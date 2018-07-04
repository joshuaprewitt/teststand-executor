/**************************************************************************/
/* LabWindows/CVI User Interface Resource (UIR) Include File              */
/* Copyright (c) National Instruments 2014. All Rights Reserved.          */
/*                                                                        */
/* WARNING: Do not add to, delete from, or otherwise modify the contents  */
/*          of this include file.                                         */
/**************************************************************************/

#include <userint.h>

#ifdef __cplusplus
    extern "C" {
#endif

     /* Panels and Controls: */

#define  UUT                              1
#define  UUT_POWER                        2       /* control type: radioButton, callback function: (none) */
#define  UUT_VIDEO                        3       /* control type: radioButton, callback function: (none) */
#define  UUT_CPU                          4       /* control type: radioButton, callback function: (none) */
#define  UUT_ROM                          5       /* control type: radioButton, callback function: (none) */
#define  UUT_RAM                          6       /* control type: radioButton, callback function: (none) */
#define  UUT_KEYBOARD                     7       /* control type: radioButton, callback function: (none) */
#define  UUT_DONE                         8       /* control type: command, callback function: SetupUICallback */
#define  UUT_CHECKTESTSWHICHSHOULD        9       /* control type: textMsg, callback function: (none) */
#define  UUT_NUMBERSLISTPICTURE           10      /* control type: picture, callback function: (none) */
#define  UUT_PICTURE                      11      /* control type: picture, callback function: (none) */
#define  UUT_FRAME                        12      /* control type: deco, callback function: (none) */


     /* Control Arrays: */

          /* (no control arrays in the resource file) */


     /* Menu Bars, Menus, and Menu Items: */

          /* (no menu bars in the resource file) */


     /* Callback Prototypes: */

int  CVICALLBACK SetupUICallback(int panel, int control, int event, void *callbackData, int eventData1, int eventData2);


#ifdef __cplusplus
    }
#endif
