<?php
$host = getenv('MYSQLHOST') ?: 'localhost';
$user = getenv('MYSQLUSER') ?: 'root';
$password = getenv('MYSQLPW') ?: '';
$database = getenv('MYSQLDB') ?: 'test';

$date = $_GET['date'] ?? date('Y-m-d');
$threshold = 180; // blood glucose spike threshold

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
$glucose_spikes = query_rows($mysqli, $glucose_spikes_sql, [$date, $threshold]);

// All glucose points
$glucose_sql = "SELECT dt.ts, fg.sgv
                FROM fact_glucose fg
                JOIN dim_time dt ON fg.time_id = dt.time_id
                WHERE dt.date = ?
                ORDER BY dt.ts";
$glucose = query_rows($mysqli, $glucose_sql, [$date]);

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
var data = <?php echo json_encode(array_map(function($g){ return ['t'=>date('H:i', $g['ts']), 'y'=>$g['sgv']]; }, $glucose)); ?>;
var chart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: data.map(p => p.t),
        datasets: [{
            label: 'Glucose (mg/dL)',
            data: data.map(p => p.y),
            borderColor: 'rgba(75, 192, 192, 1)',
            tension: 0.1,
            fill: false
        }]
    },
    options: {
        scales: {
            x: {
                display: true,
                title: { display: true, text: 'Time' }
            },
            y: {
                display: true,
                title: { display: true, text: 'mg/dL' }
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
<h2>Glucose Spikes (>= <?php echo $threshold; ?> mg/dL)</h2>
<?php if ($glucose_spikes): ?>
<ul>
<?php foreach ($glucose_spikes as $g): ?>
<li><?php echo date('H:i', $g['ts']); ?> - SGV: <?php echo $g['sgv']; ?> mg/dL, Delta: <?php echo $g['delta']; ?>, Direction: <?php echo htmlspecialchars($g['direction']); ?></li>
<?php endforeach; ?>
</ul>
<?php else: ?>
<p>No glucose spikes.</p>
<?php endif; ?>
</body>
</html>
