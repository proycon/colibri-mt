#!/bin/bash

#Your experiment directory
EXPDIR=/scratch/proycon/colibri-mt/

#Training data - No *.txt extension, will be appended automatically, these files are expected to be in your $EXPDIR
TRAINSOURCE=europarl50k-en-train
TRAINTARGET=europarl50k-fr-train

#Test data - o *.txt extension, will be appended automatically, these files are expected to be in your $EXPDIR
TESTSOURCE=europarl50k-en-test
TESTTARGET=europarl50k-fr-test

#Languages
SOURCELANG=en
TARGETLANG=fr

#Colibri patternmodeller options, puts a contraint on patterns used. Stricter constraints effectively prune the phrasetable
OCCURRENCES=2
MAXLENGTH=8

#Classifier options
CLASSIFIERTYPE='X' # Can be X for experts, M for monolithic, and I for ignoring the classifier
INSTANCETHRESHOLD=2 #Classifier are only built and used if they have at least this number of instances
SCOREHANDLING='append' #Score handling: append, replace or weighed
LEFT=1 #Left context size
RIGHT=1 #Right context size
WEIGHBYOCCURRENCE=0  #Boolean: When building classifier data (-C), use exemplar weighting to reflect occurrence count, rather than duplicating instances
WEIGHBYSCORE=0 #Boolean: When building classifier data (-C), use exemplar weighting to weigh in p(t|s) from score vector

#timbl options
TIMBL_A=0
TIMBL_K=1
TIMBL_W=gr
TIMBL_M=O
TIMBL_D=Z

#Decoder options
TWEIGHTS=(1 1 1 1 1 1)  #6 values if scorehandling==append (last score is appended), 5 otherwise
LMWEIGHT=1
DWEIGHT=1
WWEIGHT=0


#$NAME will be the basis of a directory that holds all data for this experiment,
#classifier data will be in a subdir thereof (with options encoded in directory name)
#decoding output and scores will again be in a subdir of the classifier directory
NAME="europarl50k-$SOURCELANG-$TARGETLANG-t$OCCURRENCES-l$MAXLENGTH"


#########################################################

MATREXDIR=/home/proycon/mtevalscripts/

EXPSCRIPT=/vol/customopt/uvt-ru/src/colibri-mt/scripts/colibri-mt-exp.sh

. $EXPSCRIPT




