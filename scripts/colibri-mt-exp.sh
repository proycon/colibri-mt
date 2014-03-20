#!/bin/bash

blue='\e[1;34m'
red='\e[1;31m'
yellow='\e[1;33m'
magenta='\e[1;35m'
NC='\e[0m' # No Color


cd $EXPDIR

if [ ! -d "$NAME" ]; then
    mkdir $NAME
fi
cd $NAME

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
if [ "$IGNORECLASSIFIER" = "1" ]; then
    CONTEXTMOSES_EXTRAOPTIONS="-I"
else
    CONTEXTMOSES_EXTRAOPTIONS=""
fi
TWEIGHTS_COMMA=""
TWEIGHTS_OPTIONS=""
for tweight in ${TWEIGHTS[*]}; do
    if [ ! -z "${TWEIGHTS_COMMA}" ]; then
        TWEIGHTS_COMMA="${TWEIGHTS_COMMA},${tweight}"
    else
        TWEIGHTS_COMMA=$tweight
    fi
    TWEIGHTS_OPTIONS="${TWEIGHTS_OPTIONS} --tweight $tweight"
done
if [ -z $TWEIGHTS_COMMA ]; then
    echo "No tweights? tweights=$TWEIGHTS">&2
    sleep 3
    exit 2
fi
CLASSIFIERDIR="classifierdata-${CLASSIFIERTYPE}I${INSTANCETHRESHOLD}l${LEFT}r${RIGHT}$EXTRANAME"
if [ "$IGNORECLASSIFIER" = "1" ]; then
    CLASSIFIERSUBDIR="classifiers-H${SCOREHANDLING}-ignored"
else
    CLASSIFIERSUBDIR="classifiers-H${SCOREHANDLING}-ta${TIMBL_A}"
fi
if [ "$MERT" = "1" ]; then
    DECODEDIR="decode-mert"
else
    DECODEDIR="decode-T${TWEIGHTS_COMMA}-L${LMWEIGHT}-D${DWEIGHT}-W${WWEIGHT}"
fi
DECODEMERTDIR="dev-mert"

if [ -z "$THREADS" ]; then
    THREADS=1
fi


if [ "$MOSESONLY" = "1" ]; then
    echo -e "${yellow}****************** STARTING EXPERIMENT $NAME (MOSES-ONLY) *******************************${NC}" >&2
else
    echo -e "${yellow}****************** STARTING EXPERIMENT $NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR *******************************${NC}" >&2
fi



####### integrity checks ###################

if [ "$MERT" = "1" ] && [ -z $MOSESDIR ]; then
    echo -e "${red}MOSESDIR must be set when MERT is used${NC}" >&2
    sleep 3
    exit 2
fi
if [ ! -f "$EXPDIR/${TRAINSOURCE}.txt" ]; then
    echo -e "${red}TRAINSOURCE does not exist: $EXPDIR/${TRAINSOURCE}.txt ${NC}" >&2
    sleep 3
    exit 2
fi
if [ ! -f "$EXPDIR/${TRAINTARGET}.txt" ]; then
    echo -e "${red}TRAINTARGET does not exist: $EXPDIR/${TRAINTARGET}.txt ${NC}" >&2
    sleep 3
    exit 2
fi

if [ ! -f "$EXPDIR/${TESTSOURCE}.txt" ]; then
    echo -e "${red}TESTSOURCE does not exist: $EXPDIR/${TESTSOURCE}.txt ${NC}" >&2
    sleep 3
    exit 2
fi
if [ ! -f "$EXPDIR/${TESTTARGET}.txt" ]; then
    echo -e "${red}TESTTARGET does not exist: $EXPDIR/${TESTTARGET}.txt ${NC}" >&2
    sleep 3
    exit 2
fi

if [ "$MERT" = "1" ]; then
    if [ -z "$DEVSOURCE" ]; then
        echo -e "${red}MERT is enabled but no DEVSOURCE is specified!${NC}" >&2
        sleep 3
        exit 2
    fi
    if [ -z "$DEVTARGET" ]; then
        echo -e "${red}MERT is enabled but no DEVTARGET is specified!${NC}" >&2
        sleep 3
        exit 2
    fi
    if [ ! -f "$EXPDIR/${DEVSOURCE}.txt" ]; then
        echo -e "${red}DEVSOURCE does not exist: $EXPDIR/${DEVSOURCE}.txt ${NC}" >&2
        sleep 3
        exit 2
    fi
    if [ ! -f "$EXPDIR/${DEVTARGET}.txt" ]; then
        echo -e "${red}DEVTARGET does not exist: $EXPDIR/${DEVTARGET}.txt ${NC}" >&2
        sleep 3
        exit 2
    fi
    if [ ! -z "$TESTFACTOR" ]; then
        if [ -z "$DEVFACTOR" ]; then
            echo "No DEVFACTOR specified, whilst TESTFACTOR and MERT are set!" >&2
            exit 2
        fi
    fi
fi



##############################




if [ ! -f "$TARGETLANG.lm" ]; then
    echo -e "${blue}$NAME -- Building language model${NC}">&2
    ngram-count -text ../$TRAINTARGET.txt -order 3 -interpolate -kndiscount -unk -lm $TARGETLANG.lm
fi


if [ "$MOSESONLY" = "1" ]; then
    
    if [ ! -f model/phrase-table.gz ] || [ ! -f model/moses.ini ]; then
        echo -e "${blue}[$NAME (Moses only)]\nBuilding phrasetable${NC}">&2
        ln -s "$EXPDIR/$TRAINSOURCE.txt" "$EXPDIR/$NAME/corpus.$SOURCELANG"
        ln -s "$EXPDIR/$TRAINTARGET.txt" "$EXPDIR/$NAME/corpus.$TARGETLANG"    
        CMD="/vol/customopt/machine-translation/src/mosesdecoder/scripts/training/train-model.perl -external-bin-dir /vol/customopt/machine-translation/bin  -root-dir . --corpus corpus --f $SOURCELANG --e $TARGETLANG --last-step 9 --lm 0:3:$EXPDIR/$NAME/$TARGETLANG.lm"
        if [ ! -z "$REORDERING" ]; then
            CMD="$CMD -reordering $REORDERING"
        fi
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}Error in Moses${NC}" >&2
            sleep 3
            exit 2
        fi
        cp "model/phrase-table.gz" "$NAME.phrasetable.gz"
        gunzip "$NAME.phrasetable.gz"
    else
        echo -e "${magenta}[$NAME (Moses only)]\nPhrase-table already built${NC}">&2
    fi

    if [ "$MERT" = 1 ]; then
        echo -e "${blue}[$NAME (Moses only)]\nRunning MERT${NC}">&2
        if [ ! -f mert-work/moses.ini ]; then
            echo "$MOSESDIR/scripts/training/mert-moses.pl --decoder-flags=\"-threads $THREADS\" --mertdir=$MOSESDIR/mert/ ../$DEVSOURCE.txt ../$DEVTARGET.txt `which moses` model/moses.ini" >&2
            $MOSESDIR/scripts/training/mert-moses.pl --decoder-flags="-threads $THREADS" --mertdir=$MOSESDIR/mert/ ../$DEVSOURCE.txt ../$DEVTARGET.txt `which moses` model/moses.ini
            if [[ $? -ne 0 ]]; then
                echo -e "${red}Error in Moses${NC}" >&2
                sleep 3
                exit 2
            fi
        fi

        if [ ! -f output.mosesonly-mert.txt ]; then
            echo -e "${blue}[$NAME (Moses only, mert)]\nInvoking moses directly on the data (Moses-only approach, no classifiers or bypass method whatsoever)${NC}">&2
            echo "moses -threads $THREADS -f mert-work/moses.ini < ../$TESTSOURCE.txt > output.mosesonly-mert.txt">&2
            moses -threads $THREADS -f mert-work/moses.ini < ../$TESTSOURCE.txt > output.mosesonly-mert.txt
        else
            echo -e "${magenta}[$NAME (Moses only, mert)]\nMoses output already exists ${NC}">&2
        fi

        if [ ! -f output.mosesonly-mert.summary.score ]; then
            echo -e "${blue}[$NAME (Moses only, mert)]\nEvaluating${NC}">&2
            colibri-evaluate --matrexdir $MATREXDIR --input ../$TESTSOURCE.txt --ref ../$TESTTARGET.txt --out output.mosesonly-mert.txt 
        else
            echo -e "${magenta}[$NAME (Moses only, mert)]\nEvaluation already done${NC}">&2
        fi
    else
        #no mert

        if [ ! -f output.mosesonly.txt ]; then
            echo -e "${blue}[$NAME (Moses only)]\nInvoking moses directly on the data (Moses-only approach, no classifiers or bypass method whatsoever)${NC}">&2
            echo "moses -threads $THREADS -f model/moses.ini < ../$TESTSOURCE.txt > output.mosesonly.txt" >&2
            moses -threads $THREADS -f model/moses.ini < ../$TESTSOURCE.txt > output.mosesonly.txt
        else
            echo -e "${magenta}[$NAME (Moses only)]\nMoses output already exists ${NC}">&2
        fi

        if [ ! -f output.mosesonly.summary.score ]; then
            echo -e "${blue}[$NAME (Moses only)]\nEvaluating${NC}">&2
            colibri-evaluate --matrexdir $MATREXDIR --input ../$TESTSOURCE.txt --ref ../$TESTTARGET.txt --out output.mosesonly.txt 
        else
            echo -e "${magenta}[$NAME (Moses only)]\nEvaluation already done${NC}">&2
        fi
    fi



else

    if [ ! -f "$NAME.phrasetable" ]; then
        echo -e "${blue}[$NAME]\nBuilding phrasetable${NC}">&2
        ln -s "$EXPDIR/$TRAINSOURCE.txt" "$EXPDIR/$NAME/corpus.$SOURCELANG"
        ln -s "$EXPDIR/$TRAINTARGET.txt" "$EXPDIR/$NAME/corpus.$TARGETLANG"    
        CMD="/vol/customopt/machine-translation/src/mosesdecoder/scripts/training/train-model.perl -external-bin-dir /vol/customopt/machine-translation/bin  -root-dir . --corpus corpus --f $SOURCELANG --e $TARGETLANG --last-step 8"
        if [ ! -z "$REORDERING" ]; then
            CMD="$CMD -reordering $REORDERING"
        fi
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}[$NAME]\nError in Moses${NC}" >&2
            sleep 3
            exit 2
        fi
        cp "model/phrase-table.gz" "$NAME.phrasetable.gz"
        gunzip "$NAME.phrasetable.gz"
    else
        echo -e "${magenta}[$NAME]\nPhrase-table already built${NC}">&2
    fi

    if [ "$LASTSTAGE" = "buildphrasetable" ]; then
        echo "Halting after this stage as requested"
        exit 0
    fi

    if [ ! -f "$TRAINSOURCE.colibri.indexedpatternmodel" ]; then
        echo -e "${blue}[$NAME]\nBuilding source patternmodel${NC}">&2
        CMD="colibri-classencode ../$TRAINSOURCE.txt"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}[$NAME]\nError in classencode${NC}" >&2
            sleep 3
            exit 2
        fi
        CMD="colibri-patternmodeller -f $TRAINSOURCE.colibri.dat -o $TRAINSOURCE.colibri.indexedpatternmodel -l $MAXLENGTH -t $OCCURRENCES"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}[$NAME]\nError in Patternmodeller${NC}" >&2
            sleep 3
            exit 2
        fi
    else
        echo -e "${magenta}[$NAME]\nSource patternmodel already built${NC}">&2
    fi



    if [ ! -f "$TRAINTARGET.colibri.indexedpatternmodel" ]; then
        echo -e "${blue}[$NAME]\nBuilding target patternmodel${NC}">&2
        CMD="colibri-classencode ../$TRAINTARGET.txt"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}[$NAME]\nError in classencode${NC}" >&2
            sleep 3
            exit 2
        fi
        CMD="colibri-patternmodeller -f $TRAINTARGET.colibri.dat -o $TRAINTARGET.colibri.indexedpatternmodel -l $MAXLENGTH -t $OCCURRENCES"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}[$NAME]\nError in Patternmodeller${NC}" >&2
            sleep 3
            exit 2
        fi
    else
        echo -e "${magenta}[$NAME]\nTarget patternmodel already built${NC}">&2
    fi

    if [ ! -z "$TRAINFACTOR" ] && [ ! -f "${TRAINFACTOR}.colibri.indexedpatternmodel" ]; then
        echo -e "${blue}[$NAME]\nBuilding source patternmodel for factor 1${NC}">&2
        CMD="colibri-classencode ../${TRAINFACTOR}.txt"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}[$NAME]\nError in classencode${NC}" >&2
            sleep 3
            exit 2
        fi
        CMD="colibri-patternmodeller -f ${TRAINFACTOR}.colibri.dat -o ${TRAINFACTOR}.colibri.indexedpatternmodel -l $MAXLENGTH -t $OCCURRENCES"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}[$NAME]\nError in Patternmodeller${NC}" >&2
            sleep 3
            exit 2
        fi
    fi



    if [ "$LASTSTAGE" = "patternmodels" ]; then
        echo "[$NAME] - Halting after this stage as requested"
        exit 0
    fi

    if [ ! -f "$NAME.colibri.alignmodel-featconf" ]; then
        echo -e "${blue}[$NAME]\nConverting phrasetable to alignment model${NC}">&2
        CMD="colibri-mosesphrasetable2alignmodel -i $NAME.phrasetable -S $TRAINSOURCE.colibri.cls -T $TRAINTARGET.colibri.cls -o $NAME -m $TRAINSOURCE.colibri.indexedpatternmodel -M $TRAINTARGET.colibri.indexedpatternmodel -p $MIN_PTS -P $MIN_PST"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}[$NAME]\nError in colibri-mosesphrasetable2alignmodel${NC}" >&2
            sleep 3
            exit 2
        fi
    else
        echo -e "${magenta}[$NAME]\nAlignment model already built${NC}">&2
    fi

    if [ "$LASTSTAGE" = "buildalignmentmodel" ]; then
        echo "[$NAME] -- Halting after this stage as requested"
        exit 0
    fi

    if [ ! -d $CLASSIFIERDIR ]; then
        echo -e "${blue}[$NAME/$CLASSIFIERDIR]\nExtracting features and building classifiers${NC}">&2
        mkdir $CLASSIFIERDIR
        if [ ! -z "$TRAINFACTOR" ]; then
            FACTOROPTIONS="-f ${TRAINFACTOR}.colibri.dat -l $LEFT -r $RIGHT -c ${TRAINFACTOR}.colibri.cls"
        else
            FACTOROPTIONS=""
        fi
        CMD="colibri-extractfeatures -i $NAME -s $TRAINSOURCE.colibri.indexedpatternmodel -t $TRAINTARGET.colibri.indexedpatternmodel -f $TRAINSOURCE.colibri.dat -l $LEFT -r $RIGHT -c $TRAINSOURCE.colibri.cls $FACTOROPTIONS -S $TRAINSOURCE.colibri.cls -T $TRAINTARGET.colibri.cls -C -$CLASSIFIERTYPE -o $CLASSIFIERDIR -I $INSTANCETHRESHOLD $EXTRAOPTIONS"
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}[$NAME/$CLASSIFIERDIR]\nError in colibri-extractfeatures${NC}" >&2
            sleep 3
            exit 2
        fi
    else
        echo -e "${magenta}[$NAME/$CLASSIFIERDIR]\nClassifiers already built${NC}">&2
    fi

    if [ "$LASTSTAGE" = "featureextraction" ]; then
        echo "[$NAME/$CLASSIFIERDIR] -- Halting after this stage as requested"
        exit 0
    fi

    if [ ! -d $CLASSIFIERDIR/$CLASSIFIERSUBDIR ]; then
        mkdir $CLASSIFIERDIR/$CLASSIFIERSUBDIR
    fi 


    if [ ! -z "$TESTFACTOR" ]; then
        FACTOROPTIONS="-f ../$TESTFACTOR.txt"
        DEVFACTOROPTIONS="-f ../$DEVFACTOR.txt"
    else
        FACTOROPTIONS=""
        DEVFACTOROPTIONS=""
    fi

    ls $CLASSIFIERDIR/$CLASSIFIERSUBDIR/*.ibase > /dev/null
    if [ $? -ne 0 ]; then
        if [ "$IGNORECLASSIFIER" != 1 ]; then
            echo -e "${blue}[$NAME/$CLASSIFIER/$CLASSIFIERSUBDIR]\nTraining classifiers${NC}">&2
            CMD="colibri-contextmoses --train -a $NAME -S $TRAINSOURCE.colibri.cls -T $TRAINTARGET.colibri.cls -f ../$TESTSOURCE.txt $FACTOROPTIONS -w $CLASSIFIERDIR --classifierdir $CLASSIFIERDIR/$CLASSIFIERSUBDIR --threads $THREADS --ta ${TIMBL_A} ${CONTEXTMOSES_EXTRAOPTIONS}"
            echo $CMD>&2
            $CMD
        fi
    fi

    if [ "$LASTSTAGE" = "trainclassifiers" ]; then
        echo "[$NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR] -- Halting after this stage as requested"
        exit 0
    fi

    if [ "$MERT" = "1" ]; then
        #Run contextmoses, and subsequently mert, on development set
        if [ ! -d "$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEMERTDIR" ] || [ ! -f "$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEMERTDIR/moses.ini" ] || [ ! -f "$CLASSIFIERDIR/$CLASSIFIERSUBDIR/test.txt" ]; then
            mkdir "$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEMERTDIR"
            echo -e "${blue}[$NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEMERTDIR]\nProcessing development data and invoking moses${NC}">&2
            CMD="colibri-contextmoses -a $NAME -S $TRAINSOURCE.colibri.cls -T $TRAINTARGET.colibri.cls -f ../$DEVSOURCE.txt $FACTOROPTIONS -w $CLASSIFIERDIR --lm $EXPDIR/$NAME/$TARGETLANG.lm -H $SCOREHANDLING --mert --ref ../$DEVTARGET.txt --classifierdir $CLASSIFIERDIR/$CLASSIFIERSUBDIR --threads $THREADS --decodedir $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEMERTDIR --mosesdir $MOSESDIR --ta ${TIMBL_A} --tk ${TIMBL_K} --td ${TIMBL_D} --tw ${TIMBL_W} --tm ${TIMBL_M} ${CONTEXTMOSES_EXTRAOPTIONS}"
            echo $CMD>&2
            $CMD
            if [[ $? -ne 0 ]]; then
                echo -e "${red}[$NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR]\nError in colibri-contextmoses${NC}" >&2
                sleep 3
                exit 2
            fi
        else
            echo -e "${magenta}[$NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR]\nMERT already ran${NC}">&2
        fi
    fi

    if [ ! -d "$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR" ] || [ ! -f "$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/moses.ini" ] || [ ! -f "$CLASSIFIERDIR/$CLASSIFIERSUBDIR/test.txt" ]; then
        mkdir "$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR"
        echo -e "${blue}[$NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR]\nProcessing test data and invoking moses${NC}">&2
        CMD="colibri-contextmoses -a $NAME -S $TRAINSOURCE.colibri.cls -T $TRAINTARGET.colibri.cls -f ../$TESTSOURCE.txt $FACTOROPTIONS -w $CLASSIFIERDIR --lm $EXPDIR/$NAME/$TARGETLANG.lm -H $SCOREHANDLING $TWEIGHTS_OPTIONS --lmweight $LMWEIGHT --dweight $DWEIGHT --wweight $WWEIGHT --classifierdir $CLASSIFIERDIR/$CLASSIFIERSUBDIR --decodedir $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR --threads $THREADS --ta ${TIMBL_A} --tk ${TIMBL_K} --td ${TIMBL_D} --tw ${TIMBL_W} --tm ${TIMBL_M} ${CONTEXTMOSES_EXTRAOPTIONS}"
        if [ "$MERT" = "1" ]; then
            CMD="$CMD --skipdecoder"
        fi
        if [ ! -z "$REORDERING" ]; then
            CMD="$CMD --reordering $REORDERING --reorderingtable reordering-table*gz"
        fi
        echo $CMD>&2
        $CMD
        if [[ $? -ne 0 ]]; then
            echo -e "${red}[$NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR]\nError in colibri-contextmoses${NC}" >&2
            sleep 3
            exit 2
        fi
        if [ "$MERT" = "1" ]; then
            #copy moses ini from mert
            cp -f $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEMERTDIR/mert-work/moses.ini $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/
            #replace phrase-table reference 
            sed -i s/[A-Za-z0-9\.//_-]*phrase-table/$CLASSIFIERDIR\/$CLASSIFIERSUBDIR\/phrase-table/ $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/moses.ini

            #run decoder (skipped earlier)
            echo "moses -threads $THREADS -f $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/moses.ini < $CLASSIFIERDIR/$CLASSIFIERSUBDIR/test.txt > $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/output.txt" >&2
            moses -threads $THREADS -f $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/moses.ini < $CLASSIFIERDIR/$CLASSIFIERSUBDIR/test.txt > $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/output.txt
            if [[ $? -ne 0 ]]; then
                echo -e "${red}[$NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR]\nError in moses${NC}" >&2
                sleep 3
                exit 2
            fi
        fi
    elif [ ! -f "$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/output.txt" ]; then
        echo -e "${blue}[$NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR]\nInvoking moses on previously generated test data${NC}">&2
        #copy back, paths are relative
        echo "moses -threads $THREADS -f $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/moses.ini < $CLASSIFIERDIR/$CLASSIFIERSUBDIR/test.txt > $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/output.txt" >&2
        moses -threads $THREADS -f $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/moses.ini < $CLASSIFIERDIR/$CLASSIFIERSUBDIR/test.txt > $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/output.txt
        if [[ $? -ne 0 ]]; then
            echo -e "${red}[$NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR]\nError in moses${NC}" >&2
            sleep 3
            exit 2
        fi
    else
        echo -e "${magenta}[$NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR]\nDecoder already ran${NC}">&2
    fi



    if [ "$LASTSTAGE" = "decoder" ]; then
        echo "[$NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR] -- Halting after this stage as requested"
        exit 0
    fi

    if [ ! -f "$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/output.summary.score" ]; then
        echo -e "${blue}[$NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR]\nEvaluating${NC}">&2
        colibri-evaluate --matrexdir $MATREXDIR --input ../$TESTSOURCE.txt --ref ../$TESTTARGET.txt --out $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/output.txt 

        echo "Classifier output is in $CLASSIFIERDIR/$CLASSIFIERSUBDIR"
        echo "Decoder output and evaluation is in $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/"
    else
        echo -e "${magenta}[$NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODERDIR]\nEvaluation already done${NC}">&2
        echo "Classifier output is in $CLASSIFIERDIR/$CLASSIFIERSUBDIR"
        echo "Decoder output and evaluation is in $CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR/"
    fi
fi

if [ "$MOSESONLY" = "1" ]; then
    echo -e "****************** FINISHED EXPERIMENT $NAME (MOSES-ONLY) *******************************" >&2
else
    echo -e "****************** FINISHED EXPERIMENT $NAME/$CLASSIFIERDIR/$CLASSIFIERSUBDIR/$DECODEDIR *******************************" >&2
fi
sleep 3

echo "All done..."
