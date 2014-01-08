#!/bin/bash

EXPDIR=/scratch/proycon/colibri-mt/

#no *.txt extension, will be appended
TRAINSOURCE=europarl50k-en-train
TRAINTARGET=europarl50k-fr-train

TESTSOURCE=europarl50k-en-test
TESTTARGET=europarl50k-fr-test

SOURCELANG=en
TARGETLANG=fr

#colibri patternmodeller options
OCCURRENCES=2
MAXLENGTH=8

CLASSIFIERTYPE="-X"
SCOREHANDLING='append'
LMWEIGHT=1
DWEIGHT=1

TIMBLOPTS="-a 0 -k 1" #not used yet, problem passing 

NAME="europarl50k-$SOURCELANG-$TARGETLANG"


LEFT=1
RIGHT=1

#########################################################

MATREXDIR=/home/proycon/mtevalscripts/

EXPSCRIPT=/vol/customopt/uvt-ru/src/colibri-mt/scripts/colibri-mt-exp.sh

. $EXPSCRIPT




