#!/bin/bash

blue='\e[1;34m'
red='\e[1;31m'
NC='\e[0m' # No Color


cd $EXPDIR

if [ ! -d "$NAME" ]; then
    mkdir $NAME
fi
cd $NAME

if [ ! -f "$NAME.phrasetable" ]; then
    echo -e "${blue}Building phrasetable${NC}">&2
    ln -s "$EXPDIR/$TRAINSOURCE.txt" "$EXPDIR/$NAME/corpus.$SOURCELANG"
    ln -s "$EXPDIR/$TRAINTARGET.txt" "$EXPDIR/$NAME/corpus.$TARGETLANG"    
    /vol/customopt/machine-translation/src/mosesdecoder/scripts/training/train-model.perl -external-bin-dir /vol/customopt/machine-translation/bin  -root-dir . --corpus corpus --f $SOURCELANG --e $TARGETLANG --last-step 8
    if [[ $? -ne 0 ]]; then
        echo -e "${red}Error in Moses${NC}" >&2
        exit 2
    fi
    mv "model/phrase-table.gz" "$NAME.phrasetable.gz"
    gunzip "$NAME.phrasetable.gz"
fi

if [ ! -f "$TRAINSOURCE.colibri.indexedpatternmodel" ]; then
    echo -e "${blue}Building source patternmodel${NC}">&2
    colibri-classencode ../$TRAINSOURCE.txt
    if [[ $? -ne 0 ]]; then
        echo -e "${red}Error in classencode${NC}" >&2
        exit 2
    fi
    colibri-patternmodeller -f $TRAINSOURCE.colibri.dat -o $TRAINSOURCE.colibri.indexedpatternmodel -l $MAXLENGTH -t $OCCURRENCES
    if [[ $? -ne 0 ]]; then
        echo -e "${red}Error in Patternmodeller${NC}" >&2
        exit 2
    fi
fi


if [ ! -f "$TRAINTARGET.colibri.indexedpatternmodel" ]; then
    echo -e "${blue}Building source patternmodel${NC}">&2
    colibri-classencode ../$TRAINTARGET.txt
    if [[ $? -ne 0 ]]; then
        echo -e "${red}Error in classencode${NC}" >&2
        exit 2
    fi
    colibri-patternmodeller -f $TRAINTARGET.colibri.dat -o $TRAINTARGET.colibri.indexedpatternmodel -l $MAXLENGTH -t $OCCURRENCES
    if [[ $? -ne 0 ]]; then
        echo -e "${red}Error in Patternmodeller${NC}" >&2
        exit 2
    fi
fi

if [ ! -f "$NAME.colibri.alignmodel-featconf" ]; then
    echo -e "${blue}Converting phrasetable to alignment model${NC}">&2
    colibri-mosesphrasetable2alignmodel -i $NAME.phrasetable -S $TRAINSOURCE.colibri.cls -T $TRAINTARGET.colibri.cls -o $NAME -m $TRAINSOURCE.colibri.indexedpatternmodel -M $TRAINTARGET.colibri.indexedpatternmodel -p 0.05 -P 0.05
    if [[ $? -ne 0 ]]; then
        echo -e "${red}Error in colibri-mosesphrasetable2alignmodel${NC}" >&2
        exit 2
    fi
fi

CLASSIFIERDIR="classifiers-l${LEFT}-r${RIGHT}"
if [ ! -d $CLASSIFIERDIR ]; then
    echo -e "${blue}Extracting features and building classifiers${NC}">&2
    mkdir $CLASSIFIERDIR
    colibri-extractfeatures -i $NAME -s $TRAINSOURCE.colibri.indexedpatternmodel -t $TRAINTARGET.colibri.indexedpatternmodel -f $TRAINSOURCE.colibri.dat -l $LEFT -r $RIGHT -c $TRAINSOURCE.colibri.cls -S $TRAINSOURCE.colibri.cls -T $TRAINTARGET.colibri.cls -C $CLASSIFIERTYPE -o $CLASSIFIERDIR
    if [[ $? -ne 0 ]]; then
        echo -e "${red}Error in colibri-extractfeatures${NC}" >&2
        exit 2
    fi
fi

ls $CLASSIFIERDIR/*.ibase > /dev/null
if [ $? -ne 0 ]; then
    echo -e "${blue}Training classifiers${NC}">&2
    CMD="colibri-contextmoses --train -a $NAME -S $TRAINSOURCE.colibri.cls -T $TRAINTARGET.colibri.cls -f ../$TESTSOURCE.txt -w $CLASSIFIERDIR"
    echo $CMD>& $CLASSIFIERDIR/*.ibase
    $CMD
fi

if [ ! -f "$TARGETLANG.lm" ]; then
    echo -e "${blue}Building language model${NC}">&2
    ngram-count -text ../$TRAINTARGET.txt -order 3 -interpolate -kndiscount -unk -lm $TARGETLANG.lm
fi

if [ ! -f "$CLASSIFIERDIR/phrase-table" ]; then
    echo -e "${blue}Processing test data and invoking moses${NC}">&2
    CMD="colibri-contextmoses -a $NAME -S $TRAINSOURCE.colibri.cls -T $TRAINTARGET.colibri.cls -f ../$TESTSOURCE.txt -w $CLASSIFIERDIR --lm $TARGETLANG.lm -H $SCOREHANDLING --lmweight $LMWEIGHT --dweight $DWEIGHT"
    echo $CMD>&2
    $CMD
    if [[ $? -ne 0 ]]; then
        echo -e "${red}Error in colibri-contextmoses${NC}" >&2
        exit 2
    fi
elif [ ! -f "$CLASSIFIERDIR/output.txt" ]; then
    echo -e "${blue}Invoking moses on previously generated test data${NC}">&2
    moses -f $CLASSIFIERDIR/moses.ini < $CLASSIFIERDIR/test.txt > $CLASSIFIERDIR/output.txt
    if [[ $? -ne 0 ]]; then
        echo -e "${red}Error in moses${NC}" >&2
        exit 2
    fi
fi


echo -e "${blue}Evaluating${NC}">&2
colibri-evaluate --matrexdir $MATREXDIR --input ../$TESTSOURCE.txt --ref ../$TESTTARGET.txt --out $CLASSIFIERDIR/output.txt 


