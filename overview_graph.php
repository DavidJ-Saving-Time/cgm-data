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
$insulin_sql = "SELECT dt.ts, dit.insulin_name, fi.units
                FROM fact_insulin fi
                JOIN dim_time dt ON fi.time_id = dt.time_id
                LEFT JOIN dim_insulin_type dit ON fi.insulin_type_id = dit.insulin_type_id
                WHERE dt.date = ?
                ORDER BY dt.ts";
$insulin = query_rows($mysqli, $insulin_sql, [$date]);

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
$glucose_points = [];
$prev_min = null;
$prev_val = null;
foreach ($glucose as $g) {
    $min = $minutes($g['ts']);
    $val = $mgdl_to_mmol((float)$g['sgv']);
    if ($prev_min !== null) {
        for ($m = $prev_min + 5; $m < $min; $m += 5) {
            $glucose_points[] = ['x' => $m, 'y' => $prev_val];
        }
    }
    $glucose_points[] = ['x' => $min, 'y' => $val];
    $prev_min = $min;
    $prev_val = $val;
}
$meal_points = array_map(function($m) use ($minutes) {
    return ['x' => $minutes($m['ts']), 'y' => (float)$m['carbs']];
}, $meals);
$insulin_points = array_map(function($i) use ($minutes) {
    return ['x' => $minutes($i['ts']), 'y' => (float)$i['units']];
}, $insulin);

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

var chart = new Chart(ctx, {
    type: 'line',
    data: {
        datasets: [
            {
                label: 'Glucose (mmol/L)',
                data: glucoseData,
                borderColor: 'rgba(75, 192, 192, 1)',
                tension: 0.1,
                fill: false,
                yAxisID: 'y',
                parsing: false,
                pointRadius: 0
            },
            {
                label: 'Meals (carbs)',
                data: mealData,
                type: 'scatter',
                backgroundColor: 'rgba(255, 99, 132, 1)',
                borderColor: 'rgba(255, 99, 132, 1)',
                yAxisID: 'y1',
                parsing: false
            },
            {
                label: 'Insulin (units)',
                data: insulinData,
                type: 'scatter',
                backgroundColor: 'rgba(54, 162, 235, 1)',
                borderColor: 'rgba(54, 162, 235, 1)',
                yAxisID: 'y1',
                parsing: false
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
                title: { display: true, text: 'mmol/L' }
            },
            y1: {
                display: true,
                position: 'right',
                grid: { drawOnChartArea: false },
                title: { display: true, text: 'Units/Carbs' }
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
