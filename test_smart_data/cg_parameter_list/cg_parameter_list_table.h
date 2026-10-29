/**
  ******************************************************************************
  * @file    cg_parameter_list_table.h
  * @brief   The parameter list, drawn as a table. Documentation only - no code.
  *
  * This file is generated automatically - DO NOT EDIT IT BY HAND.
  * Generator      : parameter_list_code_generator v01.03.01
  * Generated at   : 2026-10-29 19:44:49 +0330
  * Input file(s)  : parameter_lists/flight_parameters.xml
  * Parameters     : 16 value(s) in 1 structure(s)
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

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef CG_PARAMETER_LIST_TABLE_H
#define CG_PARAMETER_LIST_TABLE_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ----------------------------------------------------------------- */
/* Exported defines --------------------------------------------------------- */
/*
  Parameter list - values

  +-------+----+--------------------+-----------------+------------+-----------+-----+---------+--------+------------+-------+------+
  | Index | En | Name               | User Name       | Type       | ValueType | Arr | Default | Min    | Max        | Res   | Unit |
  +-------+----+--------------------+-----------------+------------+-----------+-----+---------+--------+------------+-------+------+
  | 0     | x  | EngineOn           | EngineOn        | MONITORING | bool_t    | 1   | FALSE   | 0      | 1          | 1     | -    |
  | 1     | x  | FlightMode         | FlightMode      | SETTING    | uint8_t   | 1   | 0       | 0      | 5          | 1     | -    |
  | 2     | x  | ElevatorTrim       | ElevatorTrim    | SETTING    | int8_t    | 1   | 0       | -20    | 20         | 1     | deg  |
  | 3     | x  | MotorRpm           | MotorRpm        | MONITORING | uint16_t  | 1   | 0       | 0      | 12000      | 1     | rpm  |
  | 4     | x  | CellTemperature    | CellTemperature | MONITORING | int16_t   | 4   | 25      | -40    | 125        | 1     | degC |
  | 8     | x  | FlightTime         | FlightTime      | MONITORING | uint32_t  | 1   | 0       | 0      | 4000000000 | 1     | s    |
  | 9     | x  | AltitudeCm         | AltitudeCm      | MONITORING | int32_t   | 1   | 0       | -50000 | 1000000    | 1     | cm   |
  | 10    | x  | Airspeed           | Airspeed        | MONITORING | float32_t | 1   | 0       | 0      | 120        | 0.1   | m/s  |
  | 11    | x  | HomeLatitude       | HomeLatitude    | SETTING    | float64_t | 1   | 35.6892 | -90    | 90         | 1e-07 | deg  |
  | -     | x  | RezaSaeedi         | -               | MONITORING | struct    | 1   | -       | -      | -          | -     | -    |
  | 12    | x  |   BirthYear        | -               | -          | uint16_t  | 1   | 2000    | 1900   | 2100       | 1     | -    |
  | 13    | x  |   CoffeeCupsPerDay | -               | -          | uint8_t   | 1   | 3       | 0      | 20         | 1     | cup  |
  | 14    | x  |   BugsFixedToday   | -               | -          | uint32_t  | 1   | 0       | 0      | 4294967295 | 1     | -    |
  | 15    | x  |   SleepHours       | -               | -          | float32_t | 1   | 4.5     | 0      | 24         | 0.5   | h    |
  +-------+----+--------------------+-----------------+------------+-----------+-----+---------+--------+------------+-------+------+

  'Index' is the index in the parameter list, the value of the matching
  #define in the defines header. A structure is not a row of the table,
  so it has no index of its own; only the values inside it have one.
*/

/*
  Parameter list - tags

  +-------+-----------------+------------------+------------+----------+---------------+-----------------+------+------+------+------+-------------+
  | Index | Name            | SystemName       | ResetProof | Loggable | LogEncryption | ParamMode       | Tag1 | Tag2 | Tag3 | Tag4 | LogID range |
  +-------+-----------------+------------------+------------+----------+---------------+-----------------+------+------+------+------+-------------+
  | 0     | EngineOn        | SYS_AC_MANAGER   |            | x        |               | PARAM_MODE_NONE | -    | -    | -    | -    | 100         |
  | 1     | FlightMode      | SYS_AC_AUTOPILOT |            | x        |               | PARAM_MODE_NONE | -    | -    | -    | -    | 101         |
  | 2     | ElevatorTrim    | SYS_AC_AUTOPILOT |            |          |               | PARAM_MODE_NONE | -    | -    | -    | -    | -           |
  | 3     | MotorRpm        | SYS_GOVERNOR     |            | x        |               | PARAM_MODE_NONE | -    | -    | -    | -    | 102         |
  | 4     | CellTemperature | SYS_AC_POWER     |            | x        |               | PARAM_MODE_NONE | -    | -    | -    | -    | 103..106    |
  | 8     | FlightTime      | SYS_AC_MANAGER   |            | x        |               | PARAM_MODE_NONE | -    | -    | -    | -    | 107         |
  | 9     | AltitudeCm      | SYS_NAV          |            | x        |               | PARAM_MODE_NONE | -    | -    | -    | -    | 108         |
  | 10    | Airspeed        | SYS_NAV          |            | x        |               | PARAM_MODE_NONE | -    | -    | -    | -    | 109         |
  | 11    | HomeLatitude    | SYS_NAV          |            |          |               | PARAM_MODE_NONE | -    | -    | -    | -    | -           |
  | -     | RezaSaeedi      | SYS_UNKNOWN      |            |          |               | PARAM_MODE_NONE | -    | -    | -    | -    | -           |
  +-------+-----------------+------------------+------------+----------+---------------+-----------------+------+------+------+------+-------------+
*/

/*
  MemoryOffset of every parameter, per tag

  +-------+-----------------------------+-------+------------+----------+-----------+
  | Index | Name                        | Bytes | SystemName | Loggable | ParamMode |
  +-------+-----------------------------+-------+------------+----------+-----------+
  | 0     | EngineOn                    | 1     | 0          | 0        | 0         |
  | 1     | FlightMode                  | 1     | 1          | 1        | 1         |
  | 2     | ElevatorTrim                | 1     | 2          | -        | 2         |
  | 3     | MotorRpm                    | 2     | 3          | 2        | 3         |
  | 4     | CellTemperature[0]          | 2     | 5          | 4        | 5         |
  | 5     | CellTemperature[1]          | 2     | 7          | 6        | 7         |
  | 6     | CellTemperature[2]          | 2     | 9          | 8        | 9         |
  | 7     | CellTemperature[3]          | 2     | 11         | 10       | 11        |
  | 8     | FlightTime                  | 4     | 13         | 12       | 13        |
  | 9     | AltitudeCm                  | 4     | 17         | 16       | 17        |
  | 10    | Airspeed                    | 4     | 21         | 20       | 21        |
  | 11    | HomeLatitude                | 8     | 25         | -        | 25        |
  | 12    | RezaSaeedi.BirthYear        | 2     | 33         | -        | 33        |
  | 13    | RezaSaeedi.CoffeeCupsPerDay | 1     | 35         | -        | 35        |
  | 14    | RezaSaeedi.BugsFixedToday   | 4     | 36         | -        | 36        |
  | 15    | RezaSaeedi.SleepHours       | 4     | 40         | -        | 40        |
  |       | TOTAL (bytes)               |       | 44         | 24       | 44        |
  +-------+-----------------------------+-------+------------+----------+-----------+

  Every tag owns an independent counter that starts at 0 and advances by
  sizeof(value) * array size for every parameter that carries the tag.
  '-' means the tag is not active for that parameter, so its offset is 0.
*/

/* Exported macros ---------------------------------------------------------- */
/* Exported types ----------------------------------------------------------- */
/* Exported functions ------------------------------------------------------- */
/* Exported variables ------------------------------------------------------- */

#ifdef __cplusplus
}
#endif

#endif /* CG_PARAMETER_LIST_TABLE_H */

/* === Copyright (c) 2026 FAS === EOF === */
