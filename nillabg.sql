-- phpMyAdmin SQL Dump
-- version 5.2.2
-- https://www.phpmyadmin.net/
--
-- Host: localhost
-- Generation Time: Jul 17, 2025 at 08:17 AM
-- Server version: 11.8.2-MariaDB
-- PHP Version: 8.4.10

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `nillabg`
--

-- --------------------------------------------------------

--
-- Table structure for table `entries`
--

CREATE TABLE `entries` (
  `mysqlid` int(11) NOT NULL,
  `_id` varchar(255) DEFAULT NULL,
  `date` double DEFAULT NULL,
  `dateString` text DEFAULT NULL,
  `delta` double DEFAULT NULL,
  `device` text DEFAULT NULL,
  `direction` text DEFAULT NULL,
  `filtered` double DEFAULT NULL,
  `noise` int(11) DEFAULT NULL,
  `rssi` int(11) DEFAULT NULL,
  `sgv` int(11) DEFAULT NULL,
  `sysTime` text DEFAULT NULL,
  `type` text DEFAULT NULL,
  `unfiltered` double DEFAULT NULL,
  `utcOffset` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `treatments`
--

CREATE TABLE `treatments` (
  `mysqlid` int(11) NOT NULL,
  `_id` varchar(255) DEFAULT NULL,
  `carbs` double DEFAULT NULL,
  `created_at` text DEFAULT NULL,
  `duration` int(11) DEFAULT NULL,
  `enteredBy` text DEFAULT NULL,
  `eventType` text DEFAULT NULL,
  `fat` text DEFAULT NULL,
  `insulin` double DEFAULT NULL,
  `insulinInjections` text DEFAULT NULL,
  `notes` text DEFAULT NULL,
  `profile` text DEFAULT NULL,
  `protein` text DEFAULT NULL,
  `sysTime` text DEFAULT NULL,
  `timestamp` text DEFAULT NULL,
  `utcOffset` int(11) DEFAULT NULL,
  `uuid` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `entries`
--
ALTER TABLE `entries`
  ADD PRIMARY KEY (`mysqlid`);

--
-- Indexes for table `treatments`
--
ALTER TABLE `treatments`
  ADD PRIMARY KEY (`mysqlid`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `entries`
--
ALTER TABLE `entries`
  MODIFY `mysqlid` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `treatments`
--
ALTER TABLE `treatments`
  MODIFY `mysqlid` int(11) NOT NULL AUTO_INCREMENT;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
