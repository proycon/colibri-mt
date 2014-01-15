#!/bin/bash

blue='\e[1;34m'
red='\e[1;31m'
NC='\e[0m' # No Color


cd $EXPDIR

if [ ! -d "$NAME" ]; then
    mkdir $NAME
fi
cd $NAME


if [ ! -f "$TARGETLANG.lm" ]; then
    echo -e "${blue}Building language model${NC}">&2
    ngram-count -text ../$TRAINTARGET.txt -order 3 -interpolate -kndiscount -unk -lm $TARGETLANG.lm
fi

if [ ! -f "$NAME.phrasetable" ]; then
    echo -e "${blue}Building phrasetable${NC}">&2
    ln -s "$EXPDIR/$TRAINSOURCE.txt" "$EXPDIR/$NAME/corpus.$SOURCELANG"
    ln -s "$EXPDIR/$TRAINTARGET.txt" "$EXPDIR/$NAME/corpus.$TARGETLANG"    
    if [ "$MOSESONLY" = "1" ]; then
        CMD="/vol/customopt/machine-translation/src/mosesdecoder/scripts/training/train-model.perl -external-bin-dir /vol/customopt/machine-translation/bin  -root-dir . --corpus corpus --f $SOURCELANG --e $TARGETLANG --last-step 9 --lm 0:3:$EXPDIR/$NAME/$TARGETLANG.lm"
    else
        CMD="/vol/customopt/machine-translation/src/mosesdecoder/scripts/training/train-model.perl -external-bin-dir /vol/customopt/machine-translation/bin  -root-dir . --corpus corpus --f $SOURCELANG --e $TARGETLANG --last-step 8"
    fi
    echo $CMD>&2
    $CMD
    if [[ $? -ne 0 ]]; then
        echo -e "${red}Error in Moses${NC}" >&2
        exit 2
    fi
    if [ "$MOSESONLY" != "1" ]; then
        mv "model/phrase-table.gz" "$NAME.phrasetable.gz"
        gunzip "$NAME.phrasetable.gz"
    fi
fi

if [ "$MOSESONLY" = "1" ]; then
     
    echo -e "${blue}Invoking moses directly on the data (Moses-only approach, no classifiers or bypass method whatsoever)${NC}">&2
    moses -f model/moses.ini < ../$TESTSOURCE.txt > output.mosesonly.txt

    echo -e "${blue}Evaluating${NC}">&2
    colibri-evaluate --matrexdir $MATREXDIR --input ../$TESTSOURCE.txt --ref ../$TESTTARGET.txt --out output.mosesonly.txt 

else


    if [ "$LASTSTAGE" = "buildphrasetable" ]; then
        echo "Halting after this stage as requested"
        exit 0
    fi

    if [ ! -f "$TRAINSOURCE.colibri.indexedpatternmodel" ]; then
        echo -e "${blue}Building source patternmodel${NC}">&2
        CMD="colibri-classencode ../$TRAINSOURCE.txt"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}Error in classencode${NC}" >&2
            exit 2
        fi
        CMD="colibri-patternmodeller -f $TRAINSOURCE.colibri.dat -o $TRAINSOURCE.colibri.indexedpatternmodel -l $MAXLENGTH -t $OCCURRENCES"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}Error in Patternmodeller${NC}" >&2
            exit 2
        fi
    fi


    if [ ! -f "$TRAINTARGET.colibri.indexedpatternmodel" ]; then
        echo -e "${blue}Building source patternmodel${NC}">&2
        CMD="colibri-classencode ../$TRAINTARGET.txt"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}Error in classencode${NC}" >&2
            exit 2
        fi
        CMD="colibri-patternmodeller -f $TRAINTARGET.colibri.dat -o $TRAINTARGET.colibri.indexedpatternmodel -l $MAXLENGTH -t $OCCURRENCES"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}Error in Patternmodeller${NC}" >&2
            exit 2
        fi
    fi

    if [ "$LASTSTAGE" = "patternmodels" ]; then
        echo "Halting after this stage as requested"
        exit 0
    fi

    if [ ! -f "$NAME.colibri.alignmodel-featconf" ]; then
        echo -e "${blue}Converting phrasetable to alignment model${NC}">&2
        CMD="colibri-mosesphrasetable2alignmodel -i $NAME.phrasetable -S $TRAINSOURCE.colibri.cls -T $TRAINTARGET.colibri.cls -o $NAME -m $TRAINSOURCE.colibri.indexedpatternmodel -M $TRAINTARGET.colibri.indexedpatternmodel -p $MIN_PTS -P $MIN_PST"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}Error in colibri-mosesphrasetable2alignmodel${NC}" >&2
            exit 2
        fi
    fi

    if [ "$LASTSTAGE" = "buildalignmentmodel" ]; then
        echo "Halting after this stage as requested"
        exit 0
    fi

    EXTRAOPTIONS=""
    EXTRANAME=""
    if [ "$WEIGHBYOCCURRENCE" = "1" ]; then
        EXTRAOPTIONS="$EXTRAOPTIONS -w"
        EXTRANAME="${EXTRANAME}w"
    fi
    if [ "$WEIGHBYSCORE" = "1" ]; then
        EXTRAOPTIONS="$EXTRAOPTIONS -W"
        EXTRANAME="${EXTRANAME}W"
    fi
    CLASSIFIERDIR="classifierdata-${CLASSIFIERTYPE}I${INSTANCETHRESHOLD}l${LEFT}r${RIGHT}$EXTRANAME"
    if [ ! -d $CLASSIFIERDIR ]; then
        echo -e "${blue}Extracting features and building classifiers${NC}">&2
        mkdir $CLASSIFIERDIR
        CMD="colibri-extractfeatures -i $NAME -s $TRAINSOURCE.colibri.indexedpatternmodel -t $TRAINTARGET.colibri.indexedpatternmodel -f $TRAINSOURCE.colibri.dat -l $LEFT -r $RIGHT -c $TRAINSOURCE.colibri.cls -S $TRAINSOURCE.colibri.cls -T $TRAINTARGET.colibri.cls -C -$CLASSIFIERTYPE -o $CLASSIFIERDIR -I $INSTANCETHRESHOLD $EXTRAOPTIONS"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}Error in colibri-extractfeatures${NC}" >&2
            exit 2
        fi
    fi

    if [ "$LASTSTAGE" = "featureextraction" ]; then
        echo "Halting after this stage as requested"
        exit 0
    fi

    CLASSIFIERSUBDIR="classifiers-H${SCOREHANDLING}-ta${TIMBL_A}"
    if [ ! -d $CLASSIFIERDIR/$CLASSIFIERSUBDIR ]; then
        mkdir $CLASSIFIERDIR/$CLASSIFIERSUBDIR
    fi 


    ls $CLASSIFIERDIR/$CLASSIFIERSUBDIR/*.ibase > /dev/null
    if [ $? -ne 0 ]; then
        echo -e "${blue}Training classifiers${NC}">&2
        CMD="colibri-contextmoses --train -a $NAME -S $TRAINSOURCE.colibri.cls -T $TRAINTARGET.colibri.cls -f ../$TESTSOURCE.txt -w $CLASSIFIERDIR --classifierdir $CLASSIFIERDIR/$CLASSIFIERSUBDIR --ta ${TIMBL_A}"
        echo $CMD>&2
        $CMD
    fi

    if [ "$LASTSTAGE" = "trainclassifiers" ]; then
        echo "Halting after this stage as requested"
        exit 0
    fi

    TWEIGHTS_COMMA=""
    TWEIGHTS_OPTIONS=""
    for tweight in ${TWEIGHTS[*]}; do
    if [ -n $TWEIGHTS_COMMA ]; then
        TWEIGHTS_COMMA="$TWEIGHTS_COMMA,$tweight"
    else
        TWEIGHTS_COMMA="$tweight"
    fi
    TWEIGHTS_OPTIONS="$TWEIGHTS_OPTIONS --tweight $tweight"
    done

    DECODEDIR="decode-T${TWEIGHTS_COMMA}-L${LMWEIGHT}-D${DWEIGHT}-W${WWEIGHT}"
    if [ ! -d "$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR" ]; then
        mkdir "$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR"
        echo -e "${blue}Processing test data and invoking moses${NC}">&2
        CMD="colibri-contextmoses -a $NAME -S $TRAINSOURCE.colibri.cls -T $TRAINTARGET.colibri.cls -f ../$TESTSOURCE.txt -w $CLASSIFIERDIR --lm $TARGETLANG.lm -H $SCOREHANDLING $TWEIGHTS_OPTIONS --lmweight $LMWEIGHT --dweight $DWEIGHT --wweight $WWEIGHT --classifierdir $CLASSIFIERDIR/$CLASSIFIERSUBDIR --decodedir $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR --ta ${TIMBL_A} --tk ${TIMBL_K} --td ${TIMBL_D} --tw ${TIMBL_W} --tm ${TIMBL_M}"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}Error in colibri-contextmoses${NC}" >&2
            exit 2
        fi
    elif [ ! -f "$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/output.txt" ]; then
        echo -e "${blue}Invoking moses on previously generated test data${NC}">&2
        #copy back, paths are relative
        moses -f $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/moses.ini < $CLASSIFIERDIR/test.txt > $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/output.txt
        if [[ $? -ne 0 ]]; then
            echo -e "${red}Error in moses${NC}" >&2
            exit 2
        fi
    fi

    if [ "$LASTSTAGE" = "decoder" ]; then
        echo "Halting after this stage as requested"
        exit 0
    fi

    echo -e "${blue}Evaluating${NC}">&2
    colibri-evaluate --matrexdir $MATREXDIR --input ../$TESTSOURCE.txt --ref ../$TESTTARGET.txt --out $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/output.txt 

    echo "Classifier output is in $CLASSIFIERDIR/$CLASSIFIERSUBDIR"
    echo "Decoder output and evaluation is in $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/"
fi
echo "All done..."
