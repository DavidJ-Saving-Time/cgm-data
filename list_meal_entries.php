<?php
$host = getenv('MYSQLHOST') ?: 'localhost';
$user = getenv('MYSQLUSER') ?: 'root';
$password = getenv('MYSQLPW') ?: '';
$database = getenv('MYSQLDB') ?: 'test';

$mysqli = new mysqli($host, $user, $password, $database);
if ($mysqli->connect_errno) {
    die("Failed to connect to MySQL: " . $mysqli->connect_error . PHP_EOL);
}

$mysqli->set_charset('utf8mb4');

$query = "SELECT * FROM treatments WHERE eventType LIKE '%Meal Entry%'";
$result = $mysqli->query($query);
if (!$result) {
    die("Query failed: " . $mysqli->error . PHP_EOL);
}

while ($row = $result->fetch_assoc()) {
    echo json_encode($row) . PHP_EOL;
}

$result->free();
$mysqli->close();
?>
