#!/bin/bash

#Your experiment directory
export EXPDIR=`realpath .`

#Training data - No *.txt extension, will be appended automatically, these files are expected to be in your $EXPDIR
export TRAINSOURCE=test-en-train
export TRAINTARGET=test-nl-train

#Test data - No *.txt extension, will be appended automatically, these files are expected to be in your $EXPDIR
export TESTSOURCE=test-en-test
export TESTTARGET=test-nl-test

#Languages
export SOURCELANG=en
export TARGETLANG=nl

#Colibri options, puts a contraint on patterns used. Stricter constraints effectively prune the phrasetable
export OCCURRENCES=1
export MAXLENGTH=8
export MIN_PTS=0.05
export MIN_PST=0.05

#Classifier options
export CLASSIFIERTYPE='X' # Can be X for experts, M for monolithic, and I for ignoring the classifier
export INSTANCETHRESHOLD=2 #Classifier are only built and used if they have at least this number of instances
export SCOREHANDLING='replace' #Score handling: append, replace or weighed
export LEFT=1 #Left context size
export RIGHT=1 #Right context size
export WEIGHBYOCCURRENCE=0  #Boolean: When building classifier data (-C), use exemplar weighting to reflect occurrence count, rather than duplicating instances
export WEIGHBYSCORE=0 #Boolean: When building classifier data (-C), use exemplar weighting to weigh in p(t|s) from score vector

#timbl options
export TIMBL_A=0
export TIMBL_K=1
export TIMBL_W=gr
export TIMBL_M=O
export TIMBL_D=Z

#Decoder options
export TWEIGHTS=(1 1 1 1)  
export LMWEIGHT=1
export DWEIGHT=1
export WWEIGHT=0

export LASTSTAGE="featureextraction" #can be set to (in order): buildphrasetable,patternmodels, buildalignmentmodel, featureextraction, trainclassifiers to halt the script earlier

#$NAME will be the basis of a directory that holds all data for this experiment,
#classifier training data will be in a subdir thereof (with options encoded in directory name)
#classifier output date will again be in a deeper subdir 
#and decoding output and scores will again be in a deeper subdir
export NAME="test-$SOURCELANG-$TARGETLANG"


#########################################################

export MATREXDIR=/home/proycon/mtevalscripts/ #not used anyway

export EXPSCRIPT=`realpath ../scripts/colibri-mt-exp.sh`

( . $EXPSCRIPT )

export CLASSIFIERTYPE='M' # Can be X for experts, M for monolithic, and I for ignoring the classifier

( . $EXPSCRIPT )

export SCOREHANDLING='append' #Score handling: append, replace or weighed
export TWEIGHTS=(1 1 1 1 1)  

( . $EXPSCRIPT )

export CLASSIFIERTYPE='M' # Can be X for experts, M for monolithic, and I for ignoring the classifier

( . $EXPSCRIPT )

