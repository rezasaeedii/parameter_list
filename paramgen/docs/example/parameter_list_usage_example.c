/**
  ******************************************************************************
  * @file    parameter_list_usage_example.c
  * @brief   How firmware uses the code the tool generates.
  *
  * One function answers one question, in the order a newcomer asks them:
  *
  *   1. how do I start it?                          fExample_Start
  *   2. how do I read a value?                      fExample_Read
  *   3. how do I write one?                         fExample_Write
  *   4. how do I write one and tell the system?     fExample_WriteAndNotify
  *   5. how do I reach a field of a structure?      fExample_StructAccess
  *   6. how do I reach the elements of an array?    fExample_ArrayAccess
  *   7. how do I go through every parameter?        fExample_WalkTable
  *   8. how do I read only what is new to me?       fExample_ReadIfNew
  *
  * The parameters are Airspeed, Position and RezaSaeedi of the test model. The library
  * (smart_data.*, parameter_descriptor.*) is the firmware's own; every cg_*
  * file is generated. This file is not generated: the test suite compiles and
  * runs it against freshly generated code.
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

/* Includes ----------------------------------------------------------------- */
#include "parameter_list_usage_example.h"

#include "cg_parameter_list.h"

/* Private defines ---------------------------------------------------------- */
/* A reader that asks "is there something new for ME?" needs an id of its own. */
#define EXAMPLE_USER_ID     eSMART_DATA_USER_ID_1

/*
  ==============================================================================
                        ##### Exported Functions #####
  ==============================================================================
*/
/**
 * @brief Builds every smart data object, then calls
 *        fParameterList_InitCompletedCallback().
 *
 * @note  Call it once, before anything reads or writes a parameter.
 *
 * @return uint8_t 0 on success, otherwise the code of what failed.
 */
uint8_t fExample_Start(void) {

    return fParameterList_Init();
}

/**
 * @brief Reads a value.
 *
 * @note  Every type has its own function - fSmartData_F32_Read for a float32_t,
 *        fSmartData_U16_Read for a uint16_t - so the compiler checks that the
 *        object and the variable agree. Nothing is cast.
 * @note  The read fails only for a null pointer. A value nobody has written yet
 *        is not a failure: it reads as its default, and
 *        fSmartData_F32_HasBeenWrittenSoFar() tells the two cases apart.
 *
 * @return eSmartDataStatus eSMART_DATA_OK when the value came back.
 */
eSmartDataStatus fExample_Read(float32_t *pAirspeed) {

    return fSmartData_F32_Read(&Cg_SmartData_Airspeed, pAirspeed);
}

/**
 * @brief Writes a value.
 *
 * @note  The write is refused when the value is outside the minimum and the
 *        maximum of the parameter: the old value stays and the status says so.
 * @note  Every reader that asks "is there something new for me?" is told (see
 *        fExample_ReadIfNew). No change event is raised - that is what
 *        fExample_WriteAndNotify is for.
 *
 * @return eSmartDataStatus eSMART_DATA_OK when the value was stored,
 *         eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE when it was refused.
 */
eSmartDataStatus fExample_Write(float32_t airspeed) {

    return fSmartData_F32_Write(&Cg_SmartData_Airspeed, &airspeed);
}

/**
 * @brief Writes a value and raises the "this parameter changed" event.
 *
 * @note  The same range checked write, and then - only when it was accepted -
 *        fParameterDescriptor_ParameterWriteCompletedCallback() is called with
 *        the descriptor of the value. It is weak: the application defines it
 *        and hears every accepted write (a logger, a telemetry link ...).
 * @note  The table is const and the write function takes a plain pointer. It
 *        only hands the descriptor on to the callback, so the cast is safe.
 *
 * @return eParameterDescriptorStatus ePARAMETER_DESCRIPTOR_OK when it landed,
 *         ePARAMETER_DESCRIPTOR_ERROR_WRITE when the smart data refused it.
 */
eParameterDescriptorStatus fExample_WriteAndNotify(float32_t airspeed) {

    sParameterDescriptor *pDescriptor = (sParameterDescriptor *)fParameterList_GetByIndex(AIRSPEED);

    return fParameterDescriptor_WriteF32(pDescriptor, airspeed);
}

/**
 * @brief Reads a value that lives inside a structure: how many cups of coffee
 *        RezaSaeedi has a day.
 *
 * @note  A structure parameter is one C object holding the whole shape, so a
 *        field is reached by writing what it is called. A structure inside a
 *        structure is one name more: &Cg_SmartData_Position.Home.Lat. The shape
 *        has a type of its own too - sCgStruct_Home for Position.Home - for a
 *        function that wants the whole structure: f(&Cg_SmartData_Position.Home).
 * @note  The field keeps its own limits: CoffeeCupsPerDay stops at 20, so a
 *        write of 30 is refused like any other value out of range.
 *
 * @return eSmartDataStatus eSMART_DATA_OK when the value came back.
 */
eSmartDataStatus fExample_StructAccess(uint8_t *pCoffeeCups) {

    return fSmartData_U8_Read(&Cg_SmartData_RezaSaeedi.CoffeeCupsPerDay, pCoffeeCups);
}

/**
 * @brief Reads every element of an array parameter.
 *
 * @note  The C object is a real array, so an element is reached with an index.
 *        How many there are is the constant <NAME>_ARRAY_SIZE, never a field of
 *        the table. Each element is also a parameter of its own in the table:
 *        POSITION_SAMPLES_0 is the index of the first, with its own tag offsets
 *        and its own log id.
 * @note  The elements land in a buffer of the same size, one by one - sized by
 *        the same constant, so the two can never disagree.
 *
 * @return uint16_t How many elements were read.
 */
uint16_t fExample_ArrayAccess(void) {

    uint16_t count = 0U;
    int16_t rezaSaeediBuffer[POSITION_SAMPLES_ARRAY_SIZE] = {0};

    for (uint16_t index = 0U; index < POSITION_SAMPLES_ARRAY_SIZE; index++) {
        if (fSmartData_I16_Read(&Cg_SmartData_Position.Samples[index], &rezaSaeediBuffer[index]) == eSMART_DATA_OK) {
            count++;
        }
    }

    return count;
}

/**
 * @brief Goes through every parameter without knowing any of them by name.
 *
 * @note  This is what a logger, a settings menu or a telemetry link does. Each
 *        row of the table is one value - an array of N elements is N rows - and
 *        carries its name, description, log id and tags.
 * @note  One value is also found by name, as the editor shows it:
 *        fParameterList_GetByName("Position.Home.Lat").
 *
 * @return uint16_t How many values carry the Loggable tag.
 */
uint16_t fExample_WalkTable(void) {

    uint16_t loggable = 0U;

    for (uint16_t index = 0U; index < fParameterList_GetQuantity(); index++) {

        const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

        if (pDescriptor->TagLoggable != 0U) {
            /* pDescriptor->LogId names the value for the logger. Where it sits
               inside the Loggable area of PARAMETER_LIST_TAG_LOGGABLE_SIZE bytes
               is documentation, not code: see table 3 of
               cg_parameter_list_table.h, which lists every value's offset. */
            loggable++;
        }
    }

    return loggable;
}

/**
 * @brief Reads Airspeed only when it is new to THIS reader.
 *
 * @note  Every reader passes an id of its own and the object keeps one "new"
 *        flag per id, so two sub-systems reading the same value do not use up
 *        each other's notification. Right after start-up every reader is told
 *        once, so that it picks up the default.
 * @note  eSMART_DATA_ERROR_NO_NEW_DATA is the ordinary answer, not a fault: it
 *        means nothing has been written since this reader last looked.
 *
 * @return bool_t TRUE when a new value was read.
 */
bool_t fExample_ReadIfNew(float32_t *pAirspeed) {

    eSmartDataStatus status = fSmartData_F32_ReadIfIsNewForId(&Cg_SmartData_Airspeed,
                                                              pAirspeed,
                                                              EXAMPLE_USER_ID);

    return (status == eSMART_DATA_OK) ? TRUE : FALSE;
}

/**
 * @brief Runs once, at the end of fParameterList_Init(), when every parameter
 *        exists.
 *
 * @note  The generated one is weak and does nothing; an application defines its
 *        own. A good place to restore what has to survive a reset: the
 *        Reset-proof parameters share an area of
 *        PARAMETER_LIST_TAG_RESET_PROOF_SIZE bytes, and where each one sits
 *        in it is listed in cg_parameter_list_table.h.
 *
 * @return uint8_t 0 on success; anything else makes fParameterList_Init() fail.
 */
uint8_t fParameterList_InitCompletedCallback(void) {

    return 0U;
}

/* === Copyright (c) 2026 FAS === EOF === */
