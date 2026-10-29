/**
  ******************************************************************************
  * @file    nsrParamOffsets.h
  * @brief   Where each parameter sits in memory - a note, not code.
  *
  * This file is generated automatically - DO NOT EDIT IT BY HAND.
  * Generator      : parameter_list_code_generator v01.03.00
  * Generated at   : 2026-10-29 16:54:52 +0330
  * Input file(s)  : parameter_lists/sys_nav_paramTable.xml
  *                   parameter_lists/sys_ac_power_paramTable.xml
  * Parameters     : 10 value(s)
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 FAS.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */

/*
  Every line of this file is a comment: including it compiles to
  nothing.  It is here to be read.

  The values of one sub-system are laid out one after another, so a
  parameter's offset is the sum of the sizes of the ones above it in
  its own sub-system.  Each sub-system starts again at 0, the same way
  the index column of nsrParamTables.h does.

  A DISABLED parameter is not here and is not in the table either: it
  takes no index and no byte, so switching one off moves the index and
  the offset of everything after it in its sub-system.

  No padding is added between values: the offsets are a plain running
  total of the sizes.
*/

/* ---- SYS_NAV --------------------------------------------------------
     index  offset  size      type  parameter
         0       0     4     float  PR_NAV_AIRSPEED
         1       4     8    double  PR_NAV_HOME_LAT
         2      12     4   int32_t  PR_NAV_ALTITUDE_CM
         3      16     1   uint8_t  PR_NAV_GPS_SATELLITES
         4      17     2   int16_t  PR_NAV_HEADING_OFFSET
         5      19     8  uint64_t  PR_NAV_UPTIME_MS

     6 parameter(s), 27 byte(s) in total
*/

/* ---- SYS_AC_POWER ---------------------------------------------------
     index  offset  size      type  parameter
         0       0     2  uint16_t  PR_PWR_BATTERY_MV
         1       2     1    int8_t  PR_PWR_CURRENT_OFFSET
         2       3     4  uint32_t  PR_PWR_ENERGY_USED
         3       7     8   int64_t  PR_PWR_CHARGE_BALANCE

     4 parameter(s), 15 byte(s) in total
*/

