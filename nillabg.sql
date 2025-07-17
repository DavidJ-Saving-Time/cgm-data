-- phpMyAdmin SQL Dump
-- version 5.2.2
-- https://www.phpmyadmin.net/
--
-- Host: localhost
-- Generation Time: Jul 17, 2025 at 03:19 PM
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
-- Table structure for table `dim_insulin_type`
--

CREATE TABLE `dim_insulin_type` (
  `insulin_type_id` int(11) NOT NULL,
  `insulin_name` varchar(255) DEFAULT NULL,
  `insulin_class` enum('bolus','basal','unknown') DEFAULT 'unknown'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `dim_time`
--

CREATE TABLE `dim_time` (
  `time_id` int(11) NOT NULL,
  `ts` bigint(20) NOT NULL,
  `date` date DEFAULT NULL,
  `hour` int(11) DEFAULT NULL,
  `minute` int(11) DEFAULT NULL,
  `dow` int(11) DEFAULT NULL,
  `month` int(11) DEFAULT NULL,
  `year` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
-- Table structure for table `fact_glucose`
--

CREATE TABLE `fact_glucose` (
  `entry_id` int(11) NOT NULL,
  `time_id` int(11) DEFAULT NULL,
  `ts` bigint(20) DEFAULT NULL,
  `sgv` int(11) DEFAULT NULL,
  `delta` double DEFAULT NULL,
  `direction` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `fact_insulin`
--

CREATE TABLE `fact_insulin` (
  `fact_id` int(11) NOT NULL,
  `treatment_id` int(11) DEFAULT NULL,
  `time_id` int(11) DEFAULT NULL,
  `ts` bigint(20) DEFAULT NULL,
  `insulin_type_id` int(11) DEFAULT NULL,
  `units` double DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `fact_meal`
--

CREATE TABLE `fact_meal` (
  `treatment_id` int(11) NOT NULL,
  `time_id` int(11) DEFAULT NULL,
  `ts` bigint(20) DEFAULT NULL,
  `carbs` double DEFAULT NULL,
  `protein` double DEFAULT NULL,
  `fat` double DEFAULT NULL,
  `classification` enum('hypo','snack','meal') DEFAULT NULL
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
  `uuid` text DEFAULT NULL,
  `epocdate` bigint(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `dim_insulin_type`
--
ALTER TABLE `dim_insulin_type`
  ADD PRIMARY KEY (`insulin_type_id`),
  ADD UNIQUE KEY `insulin_name` (`insulin_name`);

--
-- Indexes for table `dim_time`
--
ALTER TABLE `dim_time`
  ADD PRIMARY KEY (`time_id`),
  ADD UNIQUE KEY `u_ts` (`ts`);

--
-- Indexes for table `entries`
--
ALTER TABLE `entries`
  ADD PRIMARY KEY (`mysqlid`);

--
-- Indexes for table `fact_glucose`
--
ALTER TABLE `fact_glucose`
  ADD PRIMARY KEY (`entry_id`),
  ADD KEY `time_id` (`time_id`);

--
-- Indexes for table `fact_insulin`
--
ALTER TABLE `fact_insulin`
  ADD PRIMARY KEY (`fact_id`),
  ADD KEY `time_id` (`time_id`),
  ADD KEY `insulin_type_id` (`insulin_type_id`);

--
-- Indexes for table `fact_meal`
--
ALTER TABLE `fact_meal`
  ADD PRIMARY KEY (`treatment_id`),
  ADD KEY `time_id` (`time_id`);

--
-- Indexes for table `treatments`
--
ALTER TABLE `treatments`
  ADD PRIMARY KEY (`mysqlid`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `dim_insulin_type`
--
ALTER TABLE `dim_insulin_type`
  MODIFY `insulin_type_id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `dim_time`
--
ALTER TABLE `dim_time`
  MODIFY `time_id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `entries`
--
ALTER TABLE `entries`
  MODIFY `mysqlid` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `fact_insulin`
--
ALTER TABLE `fact_insulin`
  MODIFY `fact_id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `treatments`
--
ALTER TABLE `treatments`
  MODIFY `mysqlid` int(11) NOT NULL AUTO_INCREMENT;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `fact_glucose`
--
ALTER TABLE `fact_glucose`
  ADD CONSTRAINT `fact_glucose_ibfk_1` FOREIGN KEY (`time_id`) REFERENCES `dim_time` (`time_id`);

--
-- Constraints for table `fact_insulin`
--
ALTER TABLE `fact_insulin`
  ADD CONSTRAINT `fact_insulin_ibfk_1` FOREIGN KEY (`time_id`) REFERENCES `dim_time` (`time_id`),
  ADD CONSTRAINT `fact_insulin_ibfk_2` FOREIGN KEY (`insulin_type_id`) REFERENCES `dim_insulin_type` (`insulin_type_id`);

--
-- Constraints for table `fact_meal`
--
ALTER TABLE `fact_meal`
  ADD CONSTRAINT `fact_meal_ibfk_1` FOREIGN KEY (`time_id`) REFERENCES `dim_time` (`time_id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
