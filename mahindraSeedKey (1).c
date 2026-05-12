/**
* 
* @file mahindraSeedKey.c
* @author Mahindra and Mahindra Ltd. Team Diagnostics
* @date 05-09-2017
* @brief C file for Mahindra Seed and Key algorithm for ECU access
*/

/*! \mainpage Mahindra Seed Key algorithm
 *
 * \section intro_sec Introduction
 *
 * This Software Document provides documentation which will be used to aid in
 * software development by providing the details for how the source files can be used.
 *
 * \subsection level1_sec Level 1
 * The Level 1 seed key algorithm is used to authorize certain diagnostic functions / services like write, actuator control etc.
 *
 * 
 * \subsection level2_sec Level 3
 * The Level 3 seed key algorithm is used to authorize certain diagnostic functions for flashing and entering into programming session.
 */

/****************************************************/
/*Headers											*/
/****************************************************/

#include "mahindraSeedkey.h"

/****************************************************/
/*Constants											*/
/****************************************************/

/*Constant arrays / masks level1 & level2*/
const uint32_t g_seedMaskLevel1[] = { 0xF549506A, 0x47152AB0, 0x2E31DA76, 0x53266FE2, 0x874318C0, 0x2FE296BF, 0xCB84F0FE, 0xE806EC53, 0x018F28ED, 0x487E89DE, 0xCDC1B660, 0xFC0829D3, 0x847FCE7C, 0x17E8DD4D, 0xC666FF1C, 0xBDC5DBE9 };

const uint32_t g_seedMaskLevel3[] = { 0xCDCC44AD, 0x4709A45C, 0xFDD05B8C, 0xA034C50B, 0x4E3F6FD3, 0xDB31B79B, 0xE66108D4, 0x942FDDF0, 0xC0A1E39C, 0xE856356A, 0x1F05631B, 0x908B0944, 0x49357431, 0xE17D0E7D, 0xB31B46AF, 0x2BCF9D65, 0x6F6F215B, 0xC4E48957, 0x20E79E63, 0xABABF122, 0xB925F0A4, 0xF0785F02, 0x4F7AF3F5, 0x30EC3B29, 0x63E50064, 0xEB8DDA5E, 0xD4517D00, 0xCE063AB9, 0x4CA8EC66, 0xEE87EF14, 0x39BBDF5A, 0x98F41020, 0xE844B324, 0x66AF03F3, 0x403FD5CB, 0x12D73F2D, 0x142DEC9D,
                                      0x7FF8454B, 0x18737DF4, 0x79D8080D, 0xF0D4ED45, 0x8B19F5B4, 0x2744C246, 0xEE6FEBB4, 0x657FA6BB, 0x35479CE8, 0x7BBFFBFF, 0x450BAE91, 0xF13340CA, 0xA9540109, 0xF30FD0C5, 0x6C7BF9B5, 0xCFFFF991, 0xE9D05EC6, 0x37F1E734, 0x2A885C7B, 0xFCAFA810, 0xE6163386, 0x9F58376C, 0xF47724F9, 0xA85946D3, 0xA6E00B26, 0xBC0E54CF, 0xBA6B914F, 0x3445323F, 0x11822D39, 0xF5D66C08, 0x732B39F7, 0x3A33A847, 0xBFF29266, 0x97A67FC7, 0x6076130C, 0xACAEE3E7, 0xAD978FDD,
                                      0xA5F391CA, 0xC4D793A6, 0x13F8DE67, 0xE0A14D72, 0xA432D2C3, 0x370D8EAB, 0xF1F77D3A, 0xBB23EBD8, 0x41AACDCF, 0x2D668A8C, 0x8A5FD9AC, 0x123F8795, 0xA581AA1C, 0x3F94A12F, 0x71F55259, 0x4A91A903, 0xB4AC4257, 0x1D84ECE1, 0xDC5BCC49, 0xEC01332F, 0x7E04E374, 0xA36EE85C, 0x9A77271B, 0x1ACA79BB, 0xB1C5D41A, 0x3820A25E, 0xDC410F27, 0x754929A2, 0xCCB7CDA6, 0x1051AE06, 0x3266E2BC, 0xE23E6F3C, 0x3EEFC769, 0x8FFCB1B1, 0x3B9D8408, 0xE7D840BA, 0xAF965884,
                                      0x3CB2CFFE, 0xEDD68087, 0x9B839ABC, 0x8DC8CE43, 0x3E316769, 0x4D01AA1B, 0xFD3E1212, 0x40A88E30, 0x57FC2051, 0x97774857, 0x3BD679DA, 0x7C3DF001, 0x4C2B1A62, 0xC0F27F62, 0xF8B8684D, 0x56659339, 0xF9A8DB20, 0xEF32F810, 0xFF02C6CA, 0x5526D521, 0xA71CFE65, 0xCDB66BD3, 0xD3C8D704, 0x18ABCAA3, 0x2516E0BC, 0xB7DFDB23, 0xF71ECCD4, 0xD34184B5, 0x34868ECF, 0xEDDEC9AC, 0xD2B1A352, 0x573A37EB, 0x3079BBBA, 0xA3CD3103, 0x7C1052A1, 0x5673B92E, 0xDF70399E,
                                      0xE189392E, 0x744FFEED, 0x4954AF94, 0xA39C7FE3, 0x379AE82A, 0x9DB0B4A4, 0x510EB251, 0x4321FA4F, 0xA439AC3B, 0x1EDBD29F, 0xA257A930, 0xA3A6FECA, 0x5375637D, 0x1B65AB6D, 0x62C09DDC, 0xB14E2101, 0x1278C4C7, 0xE2D02410, 0x87350CB8, 0xBA13721C, 0xFE066302, 0x24AC1ECD, 0x826A0050, 0xCADB40D7, 0xCD20ACF0, 0x1D448341, 0xF7BE82C9, 0x6EB6F577, 0x89ED3E60, 0xD614E39B, 0xF656834E, 0x7BCBB2F0, 0x94EE6403, 0x7FC614D3, 0x11904C94, 0xEF601D04, 0xD217CE8D,
                                      0x504C286B, 0x38F022F8, 0xB0C44C67, 0xB39C9E57, 0x17E8403C, 0xDCE7768B, 0x1F0F69C0, 0xA5F4CB47, 0xFC5F7A46, 0x8FB747DA, 0xAF063DA2, 0x7C9814EA, 0x24290A8B, 0x58A88EBB, 0xB5E54DDB, 0xE6F9A1C9, 0x703DAA55, 0x95EF92DF, 0x595ED44A, 0x16552CC8, 0x2B747059, 0x662610D1, 0x328BE27F, 0x7DD29C36, 0xA5FF8C98, 0x38AA86B8, 0xA7765949, 0x56B5C495, 0x54A05334, 0x1B480216, 0x48339FC6, 0xA6274199, 0x445171E9, 0x2736FCC9, 0x44A468D2, 0x76ED4B20, 0x65B48559,
                                      0x1308521A, 0xC4D27CE7, 0xB8EF54C6, 0x47CD8908, 0xA17B2F67, 0xE4088DA1, 0xC480B792, 0xAFF5B3EE, 0x2A6DFD68, 0x19BB5062, 0x42CB6F28, 0x7E86811A, 0x19819940, 0x3D560926, 0x1B77BD54, 0x27F673D0, 0xC00D84D3, 0x27128926, 0xFAFF6311, 0xB8B2CD2E, 0x792226DE, 0x4BB270D9, 0xEBC71624, 0xF6E1ED2F, 0x9432A2BC, 0xB1DD04AD, 0xB2FDA210, 0xAE08F7D1, 0x547BDEDE, 0x93E5065B, 0x9E06C0C9, 0x5EDC92AC, 0x8D771DBD, 0xA799B197 };

/****************************************************/
/*Structures							*/
/****************************************************/

typedef struct
{
    uint32_t seedR;
    uint32_t seedL;
} seed_t;

/****************************************************/
/*Function Declarations								*/
/****************************************************/

static uint32_t rotateLevel1( uint32_t seedXored );
static uint64_t rotateLevel3_uint64( uint64_t seed );
static uint32_t rotateLeft( uint32_t value, uint8_t shiftCount, uint8_t seedSize );
static uint32_t rotateRight( uint32_t value, uint8_t shiftCount, uint8_t seedSize );
static uint64_t rotateLeft_uint64( uint64_t value, uint8_t shiftCount, uint8_t seedSize );
static uint64_t rotateRight_uint64( uint64_t value, uint8_t shiftCount, uint8_t seedSize );
static uint32_t findDataMask( uint32_t seedXored );
static uint64_t keyShift( uint64_t tempKey, uint16_t meanCount );
static void findLargestByte( uint64_t seed, uint8_t *p_largestByte );
static seed_t seedSeparateLeftRight( uint64_t seed, uint8_t largestByte );
static seed_t rotateLevel3( uint32_t seedL, uint32_t seedR );

/****************************************************/
/*Functions										*/
/****************************************************/

/** @brief Function to generate key by using Level 1 seed key algorithm of Mahindra.
 *
 *  @param uint32_t seed: Random seed value
 *  @param uint32_t *p_key: Pointer to the key calculated by the function.
 *  @return uint8_t Error status
 */
extern uint8_t
generateKeyLevel1( uint32_t seed, uint32_t *p_key )
{
    uint32_t seedXored     = 0;
    uint16_t seedMaskIndex = 0;
    uint32_t keyTemp       = 0;
    seedKeyError status    = SEED_OK;

    if ( seed != ( uint32_t )0 )
    {
        seedMaskIndex = ( uint16_t )( seed & L1_MASK_SEED_XOR_INDEX );
        seedXored     = ( uint32_t )( seed ^ ( g_seedMaskLevel1[ seedMaskIndex ] ) );
        keyTemp       = rotateLevel1( seedXored );
        status        = SEED_OK;
    }
    else
    {
        status = SEED_ERROR;
    }

    *p_key = keyTemp;
    return ( uint8_t )status;
}

/** @brief Rotate operation for level 1 algorithm.
 *
 *  @param uint32_t seedXored: Xored seed value 
 *  @return uint32_t key: Final Key for Level 1
 */
static uint32_t
rotateLevel1( uint32_t seedXored )
{
    uint32_t key        = 0;
    uint8_t rotateCount = 0;
    rotateCount         = ( uint8_t )( ( seedXored & L1_MASK_ROTATE_COUNT ) >> L1_SHIFT_ROTATE_COUNT );
    if ( rotateCount != 0 )
    {
        if ( ( seedXored & L1_MASK_ROTATE_DIR ) != 0 )
        {
            key = rotateRight( seedXored, rotateCount, ( uint8_t )sizeof( uint32_t ) * BYTE );
        }
        else
        {
            key = rotateLeft( seedXored, rotateCount, ( uint8_t )sizeof( uint32_t ) * BYTE );
        }
    }
    else
    {
        key = seedXored;
    }

    return key;
}

/** @brief Function to generate key by using Level 1 seed key algorithm of Mahindra.
 *
 *  @param uint64_t seed: Random seed value
 *  @param uint64_t *p_key: Pointer to the key calculated by the function.
 *  @return uint8_t Error status
 */
uint8_t
generateKeyLevel3( uint64_t seed, uint64_t *p_key )
{
    uint8_t largestByte      = 0;
    uint8_t status           = 0;
    uint32_t seedXored       = 0;
    uint64_t seedRotatedMain = 0;
    uint32_t mask            = 0;
    uint64_t shiftReg        = 0;
    uint64_t tempKey         = 0;
    uint64_t tempCount       = 0;
    uint16_t meanCount       = 0;
    uint8_t bit              = 0;
    seed_t seedSeperatedLR;
    seed_t seedRotatedLR;
    if ( seed != ( uint64_t )0 )
    {
        status = ( uint8_t )0;

        findLargestByte( seed, &largestByte );

        seedSeperatedLR = seedSeparateLeftRight( seed, largestByte );

        seedRotatedLR = rotateLevel3( seedSeperatedLR.seedL, seedSeperatedLR.seedR );

        seedXored = seedRotatedLR.seedL ^ seedRotatedLR.seedR;
        if ( seedXored == 0 )
            seedXored = ( MASK_32 - ( seedRotatedLR.seedL & seedRotatedLR.seedR ) );

        seedRotatedMain = rotateLevel3_uint64( seed );

        mask = findDataMask( seedXored );

        shiftReg = ( ( ( uint64_t )seedXored << WORD_LEN_32 ) | mask );

        tempKey = seedRotatedMain ^ shiftReg;
        if ( tempKey == 0 )
            tempKey = ( MASK_64 - ( seedRotatedMain & shiftReg ) );

        tempCount = seedRotatedMain | shiftReg;
        for ( bit = 0; bit < BYTE; bit++ )
        {
            meanCount += ( uint16_t )( ( tempCount & ( ( uint64_t )L3_MASK_COUNT_MEAN << ( bit * BYTE ) ) ) >> ( bit * BYTE ) );
        }

        meanCount = meanCount / BYTE;

        *p_key = keyShift( tempKey, meanCount );
        if ( *p_key == ( uint64_t )0 )
        {
            status++;
        }
    }
    else
    {
        status++;
    }

    return status;
}

/** @brief Finds the largest byte in the seed for level 3 algorithm.
 *
 *  @param uint64_t seed: Xored seed value 
 *  @param uint8_t p_largestByte: Pointer to the location where the largest byte has to be stored
 * 	@return void. 
 */
static void
findLargestByte( uint64_t seed, uint8_t *p_largestByte )
{
    uint8_t temp = 0;
    uint8_t bit;
    *p_largestByte = 0;

    for ( bit = 0; bit < BYTE; bit++ )
    {
        temp = ( uint8_t )( ( seed & ( ( uint64_t )MASK_BYTE << bit * BYTE ) ) >> bit * BYTE );
        if ( temp > *p_largestByte )
        {
            *p_largestByte = temp;
        }
    }
}

/** @brief Separates the Seed into seed left and seed right each of size uint32_t level 3 algorithm.
 *
 *  @param uint64_t seed: Seed value.
 *  @param uint8_t largestByte: largest byte has to be returned by findLargestByte.
 * 	@return seed_t seedSeparate: Returns the separated seed in a structure.  
 */
static seed_t
seedSeparateLeftRight( uint64_t seed, uint8_t largestByte )
{
    uint8_t bit;
    uint8_t seedModified[ BYTE ];
    uint8_t seedModifiedLR[ BYTE ];
    uint8_t cnt_r    = 0;
    uint8_t cnt_l    = 0;
    uint8_t cnt_seed = 0x0;
    uint8_t bitVal   = 0;
    seed_t seedSeparate;

    seedSeparate.seedL = 0;
    seedSeparate.seedR = 0;

    for ( bit = ( uint8_t )0; bit < BYTE; bit++ )
    {
        seedModified[ bit ] = ( ( seed & ( ( uint64_t )MASK_BYTE << ( BYTE - 1 - bit ) * BYTE ) ) >> ( BYTE - 1 - bit ) * BYTE );
    }

    for ( bit = ( uint8_t )0; bit < BYTE; bit++ )
    {
        bitVal = ( largestByte & ( ( uint8_t )1 << bit ) );
        if ( ( bitVal != 0 ) && ( cnt_l < BYTE / 2 ) )
        {
            seedModifiedLR[ cnt_l ] = seedModified[ bit ];
            cnt_seed |= ( ( uint8_t )1 << bit );
            cnt_l++;
        }
        else if ( ( bitVal == ( uint8_t )0 ) && ( cnt_r < BYTE / 2 ) )
        {
            seedModifiedLR[ ( ( uint8_t )BYTE / 2 ) + cnt_r ] = seedModified[ bit ];
            cnt_seed |= ( ( uint8_t )1 << bit );
            cnt_r++;
        }
        else
        {
            cnt_seed |= ( ( uint8_t )0 << bit );
        }
    }

    if ( cnt_r != cnt_l )
    {
        if ( cnt_r < cnt_l )
        {
            for ( bit = ( uint8_t )0; bit < BYTE; bit++ )
            {
                if ( ( cnt_seed & ( ( uint8_t )1 << bit ) ) == ( uint8_t )0 )
                {
                    seedModifiedLR[ ( BYTE / 2 ) + cnt_r ] = seedModified[ bit ];
                    cnt_seed |= ( 1 << bit );
                    cnt_r++;
                }
            }
        }
        else
        {
            for ( bit = ( uint8_t )0; bit < BYTE; bit++ )
            {
                if ( ( cnt_seed & ( ( uint8_t )1 << bit ) ) == ( uint8_t )0 )
                {
                    seedModifiedLR[ cnt_l ] = seedModified[ bit ];
                    cnt_seed |= ( ( uint8_t )1 << bit );
                    cnt_l++;
                }
            }
        }
    }

    for ( bit = ( uint8_t )0; bit < BYTE / 2; bit++ )
    {
        seedSeparate.seedL |= ( uint32_t )seedModifiedLR[ bit ] << ( ( BYTE / 2 - ( uint8_t )1 - bit ) * BYTE );
        seedSeparate.seedR |= ( uint32_t )seedModifiedLR[ 4 + bit ] << ( ( BYTE / 2 - ( uint8_t )1 - bit ) * BYTE );
    }

    return seedSeparate;
}

/** @brief Rotate operation for level 3 algorithm.
 *
 *  @param uint32_t seedL: seed left value.
 *  @param uint32_t seedR: seed right value.
 *  @return seed_t seed: Rotated seed value in a structure.
 */
static seed_t
rotateLevel3( uint32_t seedL, uint32_t seedR )
{
    uint8_t r_bit_left  = 0;
    uint8_t r_bit_right = 0;
    seed_t rotatedSeed;

    r_bit_left  = seedL & L3_MASK_L_SH_CNT;
    r_bit_right = ( uint8_t )( ( seedR & L3_MASK_R_SH_CNT ) >> L3_CNT_SEED_R_SH );

    if ( ( seedL & L3_MASK_SEED_L_CHECK ) != 0 )
        rotatedSeed.seedL = rotateRight( seedL, r_bit_left, ( uint8_t )sizeof( uint32_t ) * BYTE );
    else
        rotatedSeed.seedL = rotateLeft( seedL, r_bit_left, ( uint8_t )sizeof( uint32_t ) * BYTE );

    if ( ( seedR & L3_MASK_SEED_R_CHECK ) != 0 )
        rotatedSeed.seedR = rotateRight( seedR, r_bit_right, ( uint8_t )sizeof( uint32_t ) * BYTE );
    else
        rotatedSeed.seedR = rotateLeft( seedR, r_bit_right, ( uint8_t )sizeof( uint32_t ) * BYTE );

    return rotatedSeed;
}

/** @brief Rotate operation for level 3 algorithm.
 *
 *  @param uint32_t seed: seed value.
 *  @return uint32_t seed: Rotated seed value.
 */
static uint64_t
rotateLevel3_uint64( uint64_t seed )
{
    uint8_t bit   = 0;
    uint8_t count = 0;

    for ( bit = 0; bit < BYTE; bit++ )
    {
        count = ( ( seed & ( ( uint64_t )L3_MASK_COUNT_ROTATE << ( BYTE - 1 - bit ) * BYTE ) ) >> ( ( BYTE - 1 - bit ) * BYTE ) );
        if ( ( seed & ( ( uint64_t )L3_MASK_DIR_ROTATE << ( BYTE - 1 - bit ) * BYTE ) ) != 0 )
            seed = rotateRight_uint64( seed, count, WORD_LEN_64 );
        else
            seed = rotateLeft_uint64( seed, count, WORD_LEN_64 );
    }
    return seed;
}

/** @brief Finds the data mask level 3 algorithm.
 *
 *  @param uint32_t seedXored: Xored seed value.
 *  @return uint32_t value: Mask value for the seed.
 */
static uint32_t
findDataMask( uint32_t seedXored )
{
    uint32_t value;
    uint8_t count;
    uint8_t maskIndex;

    maskIndex = ( ( ( seedXored & L3_MASK_SEED_XOR_INDEX ) >> L3_CNT_SEED_R_SH ) );
    count     = ( ( g_seedMaskLevel3[ maskIndex ] & L3_MASK_SEED_XOR_CNT ) >> L3_CNT_SEED_R_SH );

    if ( ( g_seedMaskLevel3[ maskIndex ] & L3_MASK_DIR_DATA ) != ( uint32_t )0 )
        value = rotateRight( g_seedMaskLevel3[ maskIndex ], count, WORD_LEN_32 );
    else
        value = rotateLeft( g_seedMaskLevel3[ maskIndex ], count, WORD_LEN_32 );

    return value;
}

/** @brief Final shift operation level 3 algorithm.
 *
 *  @param uint64_t key: key to be shifted.
 *  @param uint16_t meanCount: Shift count.
 *  @return uint64_t key: Final key value.
 */
static uint64_t
keyShift( uint64_t key, uint16_t meanCount )
{
    uint16_t i;
    uint8_t cnt = 0;

    for ( i = 0; i < meanCount; i++ )
    {
        cnt = ( uint8_t )( ( key & ( uint64_t )L3_MASK_SEED_FIN_SH_CNT ) >> L3_MASK_SEED_FINAL_CNT );

        if ( i % ( uint16_t )2 == ( uint16_t )0 )
            key = rotateLeft_uint64( key, cnt, WORD_LEN_64 );
        else
            key = rotateRight_uint64( key, cnt, WORD_LEN_64 );

        key = key + i;
    }

    return key;
}

/** @brief Function left shift rotate (64bit).
 *
 *  @param uint64_t value: Value to be rotated
 *  @param uint8_t shiftCount: number of times to be shifted
 *  @param uint8_t seedSize: Size of the seed uint32_t or uint16_t
 *  @return uint64_t rotatedValue: Value after rotation 
 */
static uint64_t
rotateLeft_uint64( uint64_t value, uint8_t shiftCount, uint8_t seedSize )
{
    uint64_t rotatedValue;
    rotatedValue = ( ( value << shiftCount ) | ( value >> ( seedSize - shiftCount ) ) );
    return rotatedValue;
}

/** @brief Function right shift rotate (64bit).
 *
 *  @param uint64_t value: Value to be rotated
 *  @param uint8_t shiftCount: number of times to be shifted
 *  @param uint8_t seedSize: Size of the seed uint32_t or uint16_t
 *  @return uint64_t rotatedValue: Value after rotation
 */
static uint64_t
rotateRight_uint64( uint64_t value, uint8_t shiftCount, uint8_t seedSize )
{
    uint64_t rotatedValue;
    rotatedValue = ( ( value >> shiftCount ) | ( value << ( seedSize - shiftCount ) ) );
    return rotatedValue;
}

/** @brief Function left shift rotate.
 *
 *  @param uint32_t value: Value to be rotated
 *  @param uint8_t shiftCount: number of times to be shifted
 *  @param uint8_t seedSize: Size of the seed uint32_t or uint16_t
 *  @return uint32_t rotatedValue: Value after rotation 
 */
static uint32_t
rotateLeft( uint32_t value, uint8_t shiftCount, uint8_t seedSize )
{
    uint32_t rotatedValue;
    rotatedValue = ( ( value << shiftCount ) | ( value >> ( seedSize - shiftCount ) ) );
    return rotatedValue;
}

/** @brief Function right shift rotate.
 *
 *  @param uint32_t value: Value to be rotated
 *  @param uint8_t shiftCount: number of times to be shifted
 *  @param uint8_t seedSize: Size of the seed uint32_t or uint16_t
 *  @return uint32_t rotatedValue: Value after rotation
 */
static uint32_t
rotateRight( uint32_t value, uint8_t shiftCount, uint8_t seedSize )
{
    uint32_t rotatedValue;
    rotatedValue = ( ( value >> shiftCount ) | ( value << ( seedSize - shiftCount ) ) );
    return rotatedValue;
}
