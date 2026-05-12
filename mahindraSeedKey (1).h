/**

* 
* @file mahindraSeedKey.h
* @author Mahindra and Mahindra Ltd. Diagnostics team
* @date 05-09-2017
* @brief Function prototypes for Mahindra Seed and Key algorithm for ECU access
*
*/

#ifndef MAHINDRA_SEED_KEY
#define MAHINDRA_SEED_KEY

/****************************************************/
/*Headers											*/
/****************************************************/

#include <stdint.h>

/****************************************************/
/*Defines                                           */
/****************************************************/

#define L1_MASK_ROTATE_COUNT   0xF0000
#define L1_MASK_ROTATE_DIR     0x80000000
#define L1_MASK_SEED_XOR_INDEX 0xF
#define L1_SHIFT_ROTATE_COUNT  16

#define L3_MASK_R_SH_CNT        0x0F000000
#define L3_MASK_L_SH_CNT        0xF
#define L3_CNT_SEED_R_SH        24
#define L3_MASK_SEED_L_CHECK    0x00008000
#define L3_MASK_SEED_R_CHECK    0x00800000
#define L3_MASK_DIR_DATA        0x80
#define L3_MASK_SEED_XOR_CNT    0x0F000000
#define L3_MASK_SEED_XOR_INDEX  0xFF000000
#define L3_MASK_COUNT_MEAN      0xFF
#define L3_MASK_SEED_FIN_SH_CNT 0x0F00000000000000
#define L3_MASK_SEED_FINAL_CNT  56
#define L3_MASK_COUNT_ROTATE    0x0F
#define L3_MASK_DIR_ROTATE      0x80

#define BYTE        8
#define MASK_BYTE   0xFF
#define MASK_32     0xFFFFFFFF
#define MASK_64     0xFFFFFFFFFFFFFFFF
#define WORD_LEN_64 64
#define WORD_LEN_32 32

/****************************************************/
/*ErrorStates                                       */
/****************************************************/

typedef enum
{
    SEED_OK,
    SEED_ERROR
} seedKeyError;

/****************************************************/
/*Function Declarations								*/
/****************************************************/

extern uint8_t generateKeyLevel1( uint32_t seed, uint32_t *p_key );
extern uint8_t generateKeyLevel3( uint64_t seed, uint64_t *p_key );

#endif //MAHINDRA_SEED_KEY