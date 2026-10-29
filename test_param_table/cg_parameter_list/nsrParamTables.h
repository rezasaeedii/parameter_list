/**
  ******************************************************************************
  * @file    nsrParamTables.h
  * @brief   Parameter tables of every sub-system, as ADD_PARAM() lines.
  *
  * This file is generated automatically - DO NOT EDIT IT BY HAND.
  * Generator      : parameter_list_code_generator v01.03.01
  * Generated at   : 2026-10-29 19:44:45 +0330
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

//WARNING: Order of subsytems should comply SYS_GS_ enum (at least for last system)
//WARNING: DO NOT ADD NEW ITEMS BETWEEN OLD ITEM

//ADD_PARAM(data type, TYPE_ENUM, PR_NAME, "gs name", SYS_NAME, param index, default value, min, max, resolution, mode (0 is recommended), address (0 :: auto), "description")

#define PARAM_MODE_NONE             (0)
#define PARAM_MODE_USER             (1)
#define PARAM_MODE_READ_ONLY        (2)
#define PARAM_MODE_PRODUCT_TYPE     (3)
#define PARAM_MODE_FACTORY          (4)
#define PARAM_MODE_CALIB            (5)
#define PARAM_MODE_TEMPORARY        (6)

#if DESIRED_SUB_SYSTEM == SYS_NAV || DESIRED_SUB_SYSTEM == SYS_ALL
ADD_PARAM(float   , TYPE_FLOAT , PR_NAV_AIRSPEED      , "Nav Airspeed"      , SYS_NAV     , 0, 0.0    , 0.0        , 120.0        , 0.1  , PARAM_MODE_READ_ONLY, 0, "Indicated airspeed.")
ADD_PARAM(double  , TYPE_DOUBLE, PR_NAV_HOME_LAT      , "Nav Home Lat"      , SYS_NAV     , 1, 35.6892, -90.0      , 90.0         , 1e-07, PARAM_MODE_USER     , 0, "Latitude of the home point.")
ADD_PARAM(int32_t , TYPE_INT32 , PR_NAV_ALTITUDE_CM   , "Nav Altitude Cm"   , SYS_NAV     , 2, 0      , -50000     , 1000000      , 1    , PARAM_MODE_READ_ONLY, 0, "Altitude above sea level.")
ADD_PARAM(uint8_t , TYPE_UINT8 , PR_NAV_GPS_SATELLITES, "Nav Gps Satellites", SYS_NAV     , 3, 0      , 0          , 64           , 1    , PARAM_MODE_READ_ONLY, 0, "Satellites the GPS receiver tracks.")
ADD_PARAM(int16_t , TYPE_INT16 , PR_NAV_HEADING_OFFSET, "Nav Heading Offset", SYS_NAV     , 4, 0      , -180       , 180          , 1    , PARAM_MODE_CALIB    , 0, "Compass mounting offset.")
ADD_PARAM(uint64_t, TYPE_UINT64, PR_NAV_UPTIME_MS     , "Nav Uptime Ms"     , SYS_NAV     , 5, 0      , 0          , 1000000000000, 1    , PARAM_MODE_READ_ONLY, 0, "Time since the navigation unit started.")

#endif

#if DESIRED_SUB_SYSTEM == SYS_AC_POWER || DESIRED_SUB_SYSTEM == SYS_ALL
ADD_PARAM(uint16_t, TYPE_UINT16, PR_PWR_BATTERY_MV    , "Pwr Battery Mv"    , SYS_AC_POWER, 0, 24000  , 0          , 60000        , 1    , PARAM_MODE_READ_ONLY, 0, "Battery voltage.")
ADD_PARAM(int8_t  , TYPE_INT8  , PR_PWR_CURRENT_OFFSET, "Pwr Current Offset", SYS_AC_POWER, 1, 0      , -50        , 50           , 1    , PARAM_MODE_FACTORY  , 0, "Current sensor zero offset.")
ADD_PARAM(uint32_t, TYPE_UINT32, PR_PWR_ENERGY_USED   , "Pwr Energy Used"   , SYS_AC_POWER, 2, 0      , 0          , 4000000000   , 1    , PARAM_MODE_READ_ONLY, 0, "Energy drawn since power-up.")
ADD_PARAM(int64_t , TYPE_INT64 , PR_PWR_CHARGE_BALANCE, "Pwr Charge Balance", SYS_AC_POWER, 3, 0      , -1000000000, 1000000000   , 1    , PARAM_MODE_TEMPORARY, 0, "Charge in minus charge out.")

#endif

