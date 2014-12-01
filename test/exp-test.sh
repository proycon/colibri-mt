#!/bin/bash

#Your experiment directory
EXPDIR=`realpath .`

#Training data - No *.txt extension, will be appended automatically, these files are expected to be in your $EXPDIR
TRAINSOURCE=test-en-train
TRAINTARGET=test-nl-train

#Test data - No *.txt extension, will be appended automatically, these files are expected to be in your $EXPDIR
TESTSOURCE=test-en-test
TESTTARGET=test-nl-test

#Languages
SOURCELANG=en
TARGETLANG=nl

#Colibri options, puts a contraint on patterns used. Stricter constraints effectively prune the phrasetable
OCCURRENCES=1
MAXLENGTH=8
MIN_PTS=0.05
MIN_PST=0.05

#Classifier options
CLASSIFIERTYPE='X' # Can be X for experts, M for monolithic, and I for ignoring the classifier
INSTANCETHRESHOLD=2 #Classifier are only built and used if they have at least this number of instances
SCOREHANDLING='replace' #Score handling: append, replace or weighed
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
TWEIGHTS=(1 1 1 1)  
LMWEIGHT=1
DWEIGHT=1
WWEIGHT=0

LASTSTAGE="featureextraction" #can be set to (in order): buildphrasetable,patternmodels, buildalignmentmodel, featureextraction, trainclassifiers to halt the script earlier

#$NAME will be the basis of a directory that holds all data for this experiment,
#classifier training data will be in a subdir thereof (with options encoded in directory name)
#classifier output date will again be in a deeper subdir 
#and decoding output and scores will again be in a deeper subdir
NAME="test-$SOURCELANG-$TARGETLANG"


#########################################################

MATREXDIR=/home/proycon/mtevalscripts/ #not used anyway

EXPSCRIPT=`realpath ../scripts/colibri-mt-exp.sh`

. $EXPSCRIPT




