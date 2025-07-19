<?php
$host = getenv('MYSQLHOST') ?: 'localhost';
$user = getenv('MYSQLUSER') ?: 'root';
$password = getenv('MYSQLPW') ?: '';
$database = getenv('MYSQLDB') ?: 'test';

$date = $_GET['date'] ?? date('Y-m-d');
$threshold_mgdl = 180; // blood glucose spike threshold in mg/dL
$mgdl_to_mmol = function($v) { return round($v / 18, 1); };
$threshold = $mgdl_to_mmol($threshold_mgdl); // threshold in mmol/L for display

$mysqli = new mysqli($host, $user, $password, $database);
if ($mysqli->connect_errno) {
    die('Failed to connect to MySQL: ' . $mysqli->connect_error);
}
$mysqli->set_charset('utf8mb4');

function query_rows($mysqli, $sql, $params) {
    $stmt = $mysqli->prepare($sql);
    if (!$stmt) {
        die('Prepare failed: ' . $mysqli->error);
    }
    $types = str_repeat('s', count($params));
    $stmt->bind_param($types, ...$params);
    if (!$stmt->execute()) {
        die('Execute failed: ' . $stmt->error);
    }
    $result = $stmt->get_result();
    $rows = [];
    while ($row = $result->fetch_assoc()) {
        $rows[] = $row;
    }
    $stmt->close();
    return $rows;
}

// Meals
$meals_sql = "SELECT dt.ts, fm.carbs, fm.protein, fm.fat, fm.classification AS meal_type
              FROM fact_meal fm
              JOIN dim_time dt ON fm.time_id = dt.time_id
              WHERE dt.date = ?
              ORDER BY dt.ts";
$meals = query_rows($mysqli, $meals_sql, [$date]);

// Insulin injections
$insulin_sql = "SELECT dt.ts, dit.insulin_name, dit.insulin_class, fi.units
                FROM fact_insulin fi
                JOIN dim_time dt ON fi.time_id = dt.time_id
                LEFT JOIN dim_insulin_type dit ON fi.insulin_type_id = dit.insulin_type_id
                WHERE dt.date = ?
                ORDER BY dt.ts";
$insulin = query_rows($mysqli, $insulin_sql, [$date]);

// Only bolus insulin should contribute to IOB calculations
$bolus_insulin = array_values(array_filter(
    $insulin,
    function ($i) { return ($i['insulin_class'] ?? null) === 'bolus'; }
));

// Glucose spikes
$glucose_spikes_sql = "SELECT dt.ts, fg.sgv, fg.delta, fg.direction
                       FROM fact_glucose fg
                       JOIN dim_time dt ON fg.time_id = dt.time_id
                       WHERE dt.date = ? AND fg.sgv >= ?
                       ORDER BY dt.ts";
$glucose_spikes = query_rows($mysqli, $glucose_spikes_sql, [$date, $threshold_mgdl]);

// All glucose points
$glucose_sql = "SELECT dt.ts, fg.sgv
                FROM fact_glucose fg
                JOIN dim_time dt ON fg.time_id = dt.time_id
                WHERE dt.date = ? AND fg.sgv > 39 -- filter out sensor errors
                ORDER BY dt.ts";
$glucose = query_rows($mysqli, $glucose_sql, [$date]);

$minutes = function($ts) { return intval(date('H', $ts)) * 60 + intval(date('i', $ts)); };

function compute_iob_points(array $insulin, callable $to_minutes, int $step = 5) {
    // Pharmacokinetic model parameters for rapid acting insulin
    // ka: absorption rate constant (per minute), typical ~0.03 min^-1
    // ke: elimination rate constant (per minute), typical ~0.008 min^-1
    $ka = 0.03;
    $ke = 0.008;
    $duration = 300; // minutes of activity window

    $entries = array_map(function($i) use ($to_minutes) {
        return ['min' => $to_minutes($i['ts']), 'units' => (float)$i['units']];
    }, $insulin);

    $points = [];
    for ($t = 0; $t <= 1440; $t += $step) {
        $iob = 0.0;
        foreach ($entries as $e) {
            $tau = $t - $e['min'];
            if ($tau >= 0 && $tau < $duration) {
                $f = ($ka / ($ka - $ke)) * (exp(-$ke * $tau) - exp(-$ka * $tau));
                $iob += $f * $e['units'];
            }
        }
        $points[] = ['x' => $t, 'y' => $iob];
    }
    return $points;
}

function compute_cob_points(array $meals, callable $to_minutes, int $step = 5) {
    $duration = 120; // minutes until carbs fully absorbed
    $entries = array_map(function($m) use ($to_minutes) {
        return ['min' => $to_minutes($m['ts']), 'carbs' => (float)$m['carbs']];
    }, $meals);

    $points = [];
    for ($t = 0; $t <= 1440; $t += $step) {
        $cob = 0.0;
        foreach ($entries as $e) {
            $tau = $t - $e['min'];
            if ($tau >= 0 && $tau < $duration) {
                $cob += $e['carbs'] * (1 - $tau / $duration);
            }
        }
        $points[] = ['x' => $t, 'y' => $cob];
    }
    return $points;
}




$glucose_points = array_map(function($g) use ($minutes, $mgdl_to_mmol) {
    return ['x' => $minutes($g['ts']), 'y' => $mgdl_to_mmol((float)$g['sgv'])];
}, $glucose);
$meal_points = [];
foreach ($meals as $m) {
    $x = $minutes($m['ts']);
    $closest = null;
    $dist = PHP_INT_MAX;
    foreach ($glucose_points as $g) {
        $d = abs($g['x'] - $x);
        if ($d < $dist) { $dist = $d; $closest = $g['y']; }
    }
    if ($closest !== null) {
        $meal_points[] = ['x' => $x, 'y' => $closest, 'carbs' => (float)$m['carbs']];
    }
}

$insulin_points = [];
foreach ($bolus_insulin as $i) {
    $x = $minutes($i['ts']);
    $closest = null;
    $dist = PHP_INT_MAX;
    foreach ($glucose_points as $g) {
        $d = abs($g['x'] - $x);
        if ($d < $dist) { $dist = $d; $closest = $g['y']; }
    }
    if ($closest !== null) {
        $insulin_points[] = ['x' => $x, 'y' => $closest, 'units' => (float)$i['units']];
    }
}
$metrics = [
    // Averaged values from compute_metrics.py (negative sensitivities flipped
    // to keep the effect direction consistent)
    'morning' => [
        'carb_ratio' => 1.37,
        'insulin_sensitivity' => 0.11
    ],
    'afternoon' => [
        'carb_ratio' => 5.26,
        'insulin_sensitivity' => 0.12
    ],
    'evening' => [
        'carb_ratio' => 5.05,
        'insulin_sensitivity' => 0.25
    ]
];

// Map minutes past midnight to a time bucket
$time_bucket = function(int $min): string {
    $hour = intdiv($min, 60);
    if ($hour >= 5 && $hour < 11) return 'morning';
    if ($hour >= 11 && $hour < 13) return 'afternoon';
    return 'evening';
};

// Pre-compute IOB and COB curves
$step = 5;
$iob_points = compute_iob_points($bolus_insulin, $minutes, $step);
$cob_points = compute_cob_points($meals, $minutes, $step);

// Linear interpolation helper
$interp = function(array $points, int $t) use ($step) {
    $index = intdiv($t, $step);
    if ($index >= count($points) - 1) return $points[count($points) - 1]['y'];
    $p1 = $points[$index];
    $p2 = $points[$index + 1];
    $ratio = ($t - $p1['x']) / ($step);
    return $p1['y'] + ($p2['y'] - $p1['y']) * $ratio;
};

$iob_at_time = function(int $t) use ($iob_points, $interp) { return $interp($iob_points, $t); };
$cob_at_time = function(int $t) use ($cob_points, $interp) { return $interp($cob_points, $t); };

// Incremental prediction model
$predicted_points = [];
if (!empty($glucose_points)) {
    $predicted_y = $glucose_points[0]['y'];
    $predicted_points[] = ['x' => 0, 'y' => $predicted_y];
    for ($t = $step; $t <= 1440; $t += $step) {
        $bucket = $time_bucket($t);
        $iob = $iob_at_time($t);
        $cob = $cob_at_time($t);
        // Change in BG is driven by the balance of carbs and insulin. Convert
        // carbs to an insulin equivalent using the carb ratio and then apply
        // insulin sensitivity.
        $insulin_equiv = ($cob / $metrics[$bucket]['carb_ratio']) - $iob;
        $predicted_y += $insulin_equiv * $metrics[$bucket]['insulin_sensitivity'];
        $predicted_points[] = ['x' => $t, 'y' => $predicted_y];
    }
}
$mysqli->close();
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Daily Overview</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
<form method="get">
<label for="date">Select date:</label>
<input type="date" id="date" name="date" value="<?php echo htmlspecialchars($date); ?>">
<input type="submit" value="View">
</form>
<h1>Overview for <?php echo htmlspecialchars($date); ?></h1>
<canvas id="glucoseChart" width="600" height="300"></canvas>
<script>
var ctx = document.getElementById('glucoseChart').getContext('2d');
var glucoseData = <?php echo json_encode($glucose_points); ?>;
var mealData = <?php echo json_encode($meal_points); ?>;
var insulinData = <?php echo json_encode($insulin_points); ?>;
var iobData = <?php echo json_encode($iob_points); ?>;
var predictedData = <?php echo json_encode($predicted_points); ?>;
var chart = new Chart(ctx, {
    type: 'line',
    data: {
        datasets: [
            {
                label: 'Glucose (mmol/L)',
                data: glucoseData,
                tension: 0.1,
                fill: false,
                yAxisID: 'y',
                parsing: false,
                pointRadius: 3,
                pointBackgroundColor: ctx => {
                    const y = ctx.parsed.y;
                    if (y > 8.4) return 'red';
                    if (y < 3.7) return 'blue';
                    return 'rgba(75, 192, 192, 1)';
                },
                segment: {
                    borderColor: ctx => {
                        const y = ctx.p0.parsed.y;
                        if (y > 8.4) return 'red';
                        if (y < 3.7) return 'blue';
                        return 'rgba(75, 192, 192, 1)';
                    }
                }
            },
            {
                label: 'Meals',
                data: mealData,
                type: 'scatter',
                backgroundColor: 'rgba(255, 99, 132, 1)',
                borderColor: 'rgba(255, 99, 132, 1)',
                yAxisID: 'y',
                parsing: false,
                pointRadius: ctx => 2 + Math.sqrt(ctx.raw.carbs || 0),
                showLine: false
            },
            {
                label: 'Insulin',
                data: insulinData,
                type: 'scatter',
                backgroundColor: 'rgba(54, 162, 235, 1)',
                borderColor: 'rgba(54, 162, 235, 1)',
                yAxisID: 'y',
                parsing: false,
                pointRadius: ctx => 2 + Math.sqrt(ctx.raw.units || 0),
                showLine: false
            },
            {
                label: 'Predicted',
                data: predictedData,
                borderColor: 'rgba(153, 102, 255, 1)',
                tension: 0.1,
                fill: false,
                yAxisID: 'y',
                parsing: false,
                pointRadius: 0
            },
            {
                label: 'IOB (units)',
                data: iobData,
                borderColor: 'rgba(255,165,0,1)',
                tension: 0.1,
                fill: false,
                yAxisID: 'y1',
                parsing: false,
                pointRadius: 0           
            }
        ]
    },
    options: {
        scales: {
            x: {
                type: 'linear',
                position: 'bottom',
                min: 0,
                max: 1440,
                ticks: {
                    callback: function(value) {
                        var h = Math.floor(value / 60);
                        var m = Math.floor(value % 60);
                        return ('0' + h).slice(-2) + ':' + ('0' + m).slice(-2);
                    }
                },
                title: { display: true, text: 'Time' }
            },
            y: {
                display: true,
                title: { display: true, text: 'mmol/L' },
                min: 2,
                max: 14
            }
        }
    }
});
</script>
<h2>Meals</h2>
<?php if ($meals): ?>
<ul>
<?php foreach ($meals as $m): ?>
<li><?php echo date('H:i', $m['ts']); ?> - <?php echo htmlspecialchars($m['meal_type'] ?: 'unknown'); ?> - Carbs: <?php echo $m['carbs']; ?> g, Protein: <?php echo $m['protein']; ?> g, Fat: <?php echo $m['fat']; ?> g</li>
<?php endforeach; ?>
</ul>
<?php else: ?>
<p>No meal data.</p>
<?php endif; ?>
<h2>Insulin Injections</h2>
<?php if ($insulin): ?>
<ul>
<?php foreach ($insulin as $i): ?>
<li><?php echo date('H:i', $i['ts']); ?> - <?php echo $i['units']; ?> units (<?php echo htmlspecialchars($i['insulin_name'] ?: 'unknown'); ?>)</li>
<?php endforeach; ?>
</ul>
<?php else: ?>
<p>No insulin data.</p>
<?php endif; ?>
<h2>Glucose Spikes (>= <?php echo $threshold; ?> mmol/L)</h2>
<?php if ($glucose_spikes): ?>
<ul>
<?php foreach ($glucose_spikes as $g): ?>
<li><?php echo date('H:i', $g['ts']); ?> - SGV: <?php echo $mgdl_to_mmol($g['sgv']); ?> mmol/L, Delta: <?php echo $mgdl_to_mmol($g['delta']); ?>, Direction: <?php echo htmlspecialchars($g['direction']); ?></li>
<?php endforeach; ?>
</ul>
<?php else: ?>
<p>No glucose spikes.</p>
<?php endif; ?>
</body>
</html>
