<?php
$host = getenv('MYSQLHOST') ?: 'localhost';
$user = getenv('MYSQLUSER') ?: 'root';
$password = getenv('MYSQLPW') ?: '';
$database = getenv('MYSQLDB') ?: 'test';

$date = $argv[1] ?? date('Y') . '-07-07';
$threshold = 180; // blood glucose spike threshold

$mysqli = new mysqli($host, $user, $password, $database);
if ($mysqli->connect_errno) {
    die("Failed to connect to MySQL: " . $mysqli->connect_error . PHP_EOL);
}
$mysqli->set_charset('utf8mb4');

function query_rows($mysqli, $sql, $params) {
    $stmt = $mysqli->prepare($sql);
    if (!$stmt) {
        die("Prepare failed: " . $mysqli->error . PHP_EOL);
    }
    $types = str_repeat('s', count($params));
    $stmt->bind_param($types, ...$params);
    if (!$stmt->execute()) {
        die("Execute failed: " . $stmt->error . PHP_EOL);
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
$meals_sql = "SELECT dt.ts, dt.hour, dt.minute, fm.carbs, fm.protein, fm.fat, fm.classification AS meal_type
              FROM fact_meal fm
              JOIN dim_time dt ON fm.time_id = dt.time_id
              WHERE dt.date = ?
              ORDER BY dt.ts";
$meals = query_rows($mysqli, $meals_sql, [$date]);

// Insulin injections
$insulin_sql = "SELECT dt.ts, dt.hour, dt.minute, dit.insulin_name, fi.units
                FROM fact_insulin fi
                JOIN dim_time dt ON fi.time_id = dt.time_id
                LEFT JOIN dim_insulin_type dit ON fi.insulin_type_id = dit.insulin_type_id
                WHERE dt.date = ?
                ORDER BY dt.ts";
$insulin = query_rows($mysqli, $insulin_sql, [$date]);

// Glucose spikes
$glucose_sql = "SELECT dt.ts, dt.hour, dt.minute, fg.sgv, fg.delta, fg.direction
                FROM fact_glucose fg
                JOIN dim_time dt ON fg.time_id = dt.time_id
                WHERE dt.date = ? AND fg.sgv >= ?
                ORDER BY dt.ts";
$glucose = query_rows($mysqli, $glucose_sql, [$date, $threshold]);

$format_ts = function($ts) {
    // dim_time.ts stores epoch seconds already
    return date('Y-m-d H:i', $ts);
};

echo "Overview for $date\n";
echo str_repeat('-', 40) . "\n";

echo "Meals:\n";
if ($meals) {
    foreach ($meals as $m) {
        $type = $m['meal_type'] ?: 'unknown';
        printf("%s - %s - Carbs: %s g, Protein: %s g, Fat: %s g\n",
            $format_ts($m['ts']), $type, $m['carbs'], $m['protein'], $m['fat']);
    }
} else {
    echo "No meal data." . PHP_EOL;
}

echo "\nInsulin Injections:\n";
if ($insulin) {
    foreach ($insulin as $i) {
        $name = $i['insulin_name'] ?: 'unknown';
        printf("%s - %s units (%s)\n",
            $format_ts($i['ts']), $i['units'], $name);
    }
} else {
    echo "No insulin data." . PHP_EOL;
}

echo "\nGlucose Spikes (>= $threshold mg/dL):\n";
if ($glucose) {
    foreach ($glucose as $g) {
        printf("%s - SGV: %s mg/dL, Delta: %s, Direction: %s\n",
            $format_ts($g['ts']), $g['sgv'], $g['delta'], $g['direction']);
    }
} else {
    echo "No glucose spikes." . PHP_EOL;
}

$mysqli->close();
?>
