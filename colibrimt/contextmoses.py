#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import

import argparse
import sys
import os
import glob
from colibricore import IndexedCorpus, ClassEncoder, ClassDecoder, IndexedPatternModel, UnindexedPatternModel, PatternModelOptions, Pattern, BEGINPATTERN, ENDPATTERN
from colibrimt.alignmentmodel import FeaturedAlignmentModel
import timbl
import pickle
import time
import shutil
from urllib.parse import quote_plus, unquote_plus

def extractcontextfeatures(classifierconf, pattern, sentence, token, factoredcorpora ):
    factorconf = classifierconf['featureconf']
    featurevector = []
    n = len(pattern)
    for factoredcorpus, factor in zip(factoredcorpora, factorconf.items(False,True,False)):
        if factor[0] is Pattern:
            _,classdecoder, leftcontext, focus, rightcontext = factor
        else:
            continue
        #print("DEBUG: Available decoders: ", repr(factorconf.decoders.keys()) ,file=sys.stderr)
        #print("DEBUG: Requested decoder: ", classdecoder ,file=sys.stderr)
        classdecoder = factorconf.decoders[classdecoder]
        #print("DEBUG: Classdecoder filename=", classdecoder.filename(),file=sys.stderr)
        #print("DEBUG: Classdecoder size=", len(classdecoder),file=sys.stderr)
        sentencelength = factoredcorpus.sentencelength(sentence)
        for i in range(token - leftcontext,token):
            if i < 0:
                unigram = BEGINPATTERN
            else:
                unigram = factoredcorpus[(sentence,i)]
            assert len(unigram) == 1
            featurevector.append(unigram.tostring(classdecoder))
        if focus:
            focuspattern = factoredcorpus[(sentence,token):(sentence,token+n)]
            assert len(focuspattern) >= 1
            featurevector.append(focuspattern.tostring(classdecoder))
        for i in range(token + n , token + n + rightcontext):
            if i >= sentencelength:
                unigram = ENDPATTERN
            else:
                unigram = factoredcorpus[(sentence,i)]
            assert len(unigram) == 1
            featurevector.append(unigram.tostring(classdecoder))
    return featurevector

def gettimbloptions(args, classifierconf):
    timbloptions = "-a " + args.ta + " -k " + args.tk + " -w " + args.tw + " -m " + args.tm + " -d " + args.td  + " -vdb -G0"
    if classifierconf['weighbyoccurrence'] or classifierconf['weighbyscore']:
        timbloptions += " -s"
    return timbloptions

EXEC_MOSES = "moses"

def main():
    parser = argparse.ArgumentParser(description="Wrapper around the Moses Decoder that adds support for context features through classifiers.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-f','--inputfile', type=str,help="Input text file; the test corpus (plain text, tokenised, one sentence per line), may be specified multiple times for each factor", action='append',required=False)
    parser.add_argument('-S','--sourceclassfile', type=str, help="Source class file", action='store',required=True)
    parser.add_argument('-T','--targetclassfile', type=str, help="Target class file", action='store',required=True)
    parser.add_argument('-a','--alignmodelfile', type=str,help="Colibri alignment model (made from phrase translation table)", action='store',default="",required=False)
    parser.add_argument('-w','--workdir', type=str,help="Working directory, should contain classifier training files", action='store',default="",required=True)
    parser.add_argument('--train', help="Train classifiers", action="store_true", default=False)
    #parser.add_argument('-O','--timbloptions', type=str, help="Options for the Timbl classifier", action="store", default="-a 0 -k 1")
    parser.add_argument('--ta', type=str, help="Timbl algorithm", action="store", default="0")
    parser.add_argument('--tk', type=str, help="Timbl k value", action="store", default="1")
    parser.add_argument('--tw', type=str, help="Timbl weighting", action="store", default="gr")
    parser.add_argument('--tm', type=str, help="Timbl feature metrics", action="store", default="O")
    parser.add_argument('--td', type=str, help="Timbl distance metric", action="store", default="Z")
    parser.add_argument('-I','--ignoreclassifier', help="Ignore classifier (for testing bypass method)", action="store_true", default=False)
    parser.add_argument('-H','--scorehandling', type=str, help="Score handling, can be 'append' (default), 'replace', or 'weighed'", action="store", default="append")
    parser.add_argument('--mosesdir', type='str',help='Path to Moses directory (required for MERT)', default="")
    parser.add_argument('--mert', action="store_true",help="Do MERT parameter tuning", required=False)
    parser.add_argument('--ref', action="store_true",help="Reference corpus (target corpus, plain text)", required=False)
    parser.add_argument('--lm', type=str, help="Language Model", action="store", default="", required=False)
    parser.add_argument('--lmorder', type=int, help="Language Model order", action="store", default=3, required=False)
    parser.add_argument('--lmweight', type=float, help="Language Model weight", action="store", default=1, required=False)
    parser.add_argument('--dweight', type=float, help="Distortion Model weight", action="store", default=1, required=False)
    parser.add_argument('--wweight', type=float, help="Word penalty weight", action="store", default=0, required=False)
    parser.add_argument('--tweight', type=float, help="Translation Model weight (may be specified multiple times for each score making up the translation model)", action="append", required=False)
    parser.add_argument('--classifierdir', type=str,help="Trained classifiers, intermediate phrase-table and test file will be written here (only specify if you want a different location than the work directory)", action='store',default="",required=False)
    parser.add_argument('--decodedir', type=str,help="Moses output will be written here (only specify if you want a different location than the work directory)", action='store',default="",required=False)
    parser.add_argument('--skipdecoder',action="store_true",default=False)
    args = parser.parse_args()
    #args.storeconst, args.dataset, args.num, args.bar

    if not os.path.isdir(args.workdir) or not os.path.exists(args.workdir + '/classifier.conf'):
        print("Work directory " + args.workdir + " or classifier configuration therein does not exist. Did you extract features and create classifier training files using colibri-extractfeatures?" ,file=sys.stderr)
        sys.exit(2)

    if args.classifierdir:
        classifierdir = args.classifierdir
    else:
        classifierdir = args.workdir

    if args.mert and not args.mosesdir:
        print("--mert requires --mosesdir to be set",file=sys.stderr)
        sys.exit(2)

    if args.decodedir:
        decodedir = args.decodedir
    else:
        decodedir = args.workdir

    f = open(args.workdir + '/classifier.conf','rb')
    classifierconf = pickle.load(f)
    f.close()

    if args.inputfile:
        #Updat classifier configuration:
        #Replace original class file with extended class file (to be generated later)
        index = 0
        for i, feature in enumerate(classifierconf['featureconf']):
            if feature[0] is Pattern:
                if index >= len(args.inputfile):
                    raise Exception("Number of input files (" + str(len(args.inputfile)) + ") is less than the number of factor-features in configuration, you need to specify all")


                C, classdecoder, leftcontext, dofocus, rightcontext = feature
                classdecoder = os.path.basename(args.inputfile[index]).replace('.txt','.colibri.cls')

                feature = (C, classdecoder,leftcontext, dofocus, rightcontext)
                classifierconf['featureconf'][i] = feature

                index += 1


    #one for each factor
    corpusfiles = []
    classfiles = []
    sourceencoders = []
    sourcedecoders = []
    testcorpus = []



    if args.inputfile:
        for i, inputfile in enumerate(args.inputfile):
            print("Processing factor #" + str(i),file=sys.stderr)
            #process inputfile
            corpusfiles.append(  os.path.basename(inputfile).replace('.txt','') + '.colibri.dat' )
            classfiles.append(  os.path.basename(inputfile).replace('.txt','') + '.colibri.cls' )

            #if os.path.exists(corpusfiles[i]) and os.path.exists(classfiles[i]):
            #    print("Notice: Re-using previously generated corpusfile and classfile",file=sys.stderr)
            #    print("Loading source class encoder and decoder",file=sys.stderr)
            #    sourceencoders.append( ClassEncoder(classfiles[i]) )
            #    sourcedecoders.append( ClassDecoder(classfiles[i]) )
            #else:
            print("Loading and extending source class encoder",file=sys.stderr)
            sourceencoders.append( ClassEncoder(args.sourceclassfile) )
            sourceencoders[i].build(inputfile)
            sourceencoders[i].save(classfiles[i])
            print("Encoding test corpus",file=sys.stderr)
            sourceencoders[i].encodefile(inputfile, corpusfiles[i])
            print("Loading source class decoder",file=sys.stderr)
            sourcedecoders.append( ClassDecoder(classfiles[i]) )

            print("Loading test corpus",file=sys.stderr)
            testcorpus.append( IndexedCorpus(corpusfiles[i]) )

    print("Loading decoders for feature configuration",file=sys.stderr)
    classifierconf['featureconf'].loaddecoders(*sourcedecoders)

    if args.inputfile and args.alignmodelfile:

        print("Loading target encoder",file=sys.stderr)
        targetencoder = ClassEncoder(args.targetclassfile)
        print("Loading target decoder",file=sys.stderr)
        targetdecoder = ClassDecoder(args.targetclassfile)

        print("Loading alignment model (may take a while)",file=sys.stderr)
        alignmodel = FeaturedAlignmentModel()
        alignmodel.load(args.alignmodelfile)

        print("Building constraint model of source patterns",file=sys.stderr)
        #constain model is needed to constrain the test model
        constraintmodel = UnindexedPatternModel()
        for pattern in alignmodel.sourcepatterns():
            constraintmodel.add(pattern)

        print("Building patternmodel on test corpus",file=sys.stderr)
        options = PatternModelOptions(mintokens=1)
        testmodel = IndexedPatternModel()
        testmodel.trainconstrainedbyunindexedmodel(corpusfiles[0], options, constraintmodel)
        print("Unloading constraint model",file=sys.stderr)
        del constraintmodel
    elif args.train and args.inputfile:
        if not args.alignmodelfile:
            print("No alignment model specified (-a)",file=sys.stderr)
        sys.exit(2)
    elif not args.train:
        if not args.inputfile:
            print("No input file specified (-f)",file=sys.stderr)
        if not args.alignmodelfile:
            print("No alignment model specified (-a)",file=sys.stderr)
        sys.exit(2)

    if args.train:
        #training mode
        if args.inputfile:
            print("Training classifiers (constrained by test data)",file=sys.stderr)
        else:
            print("Training all classifiers (you may want to constrain by test data using -f)",file=sys.stderr)
        if 'monolithic' in classifierconf and classifierconf['monolithic']:
            #monolithic
            trainfile = args.workdir + "/train"
            #build a classifier
            print("Training monolithic classifier " + trainfile,file=sys.stderr)
            timbloptions = gettimbloptions(args, classifierconf)
            if args.classifierdir:
                #ugly hack since we want ibases in a different location
                trainfilecopy = trainfile.replace(args.workdir, args.classifierdir)
                shutil.copyfile(trainfile+".train", trainfilecopy+".train")
                trainfile = trainfilecopy
            classifier = timbl.TimblClassifier(trainfile, timbloptions)
            classifier.train()
            classifier.save()
            if args.classifierdir:
                #remove copy
                os.unlink(trainfile+".train")
        else:
            #experts
            for trainfile in glob.glob(args.workdir + "/*.train"):
                if args.inputfile:
                    sourcepattern_s = unquote_plus(os.path.basename(trainfile.replace('.train','')))
                    sourcepattern = sourceencoders[0].buildpattern(sourcepattern_s)
                    if not sourcepattern in testmodel:
                        continue

                #build a classifier
                print("Training " + trainfile,file=sys.stderr)
                timbloptions = gettimbloptions(args, classifierconf)
                if args.classifierdir:
                    #ugly hack since we want ibases in a different location
                    trainfilecopy = trainfile.replace(args.workdir, args.classifierdir)
                    shutil.copyfile(trainfile, trainfilecopy)
                    trainfile = trainfilecopy
                classifier = timbl.TimblClassifier(trainfile.replace('.train',''), timbloptions)
                classifier.train()
                classifier.save()
                if args.classifierdir:
                    #remove copy
                    os.unlink(trainfile)
    else:
        #TEST
        if not args.inputfile:
            print("Specify an input file (-f)",file=sys.stderr)
            sys.exit(2)


        print("Writing intermediate test data",file=sys.stderr)
        #write intermediate test data (consisting only of indices AND unknown words) and
        f = open(classifierdir + "/test.txt",'w',encoding='utf-8')
        for sentencenum, line in enumerate(testcorpus[0].sentences()):
            sentenceindex = sentencenum + 1
            print("@" + str(sentenceindex),file=sys.stderr)
            tokens = [] #actual string representations
            for tokenindex,pattern in enumerate(line):
                #is this an uncovered word? check using testmodel (which is constrained by alignment model source patterns)
                if not testmodel.covered( (sentenceindex, tokenindex) ):
                    tokens.append(pattern.tostring(sourcedecoders[0]))
                else:
                    tokens.append(str(sentenceindex) + "_" + str(tokenindex))
            f.write(" ".join(tokens) + "\n")
        f.close()

        classifierindex = set()
        if classifierconf['monolithic']:
            print("Loading classifier index for monolithic classifier",file=sys.stderr)

            with open(args.workdir + "/sourcepatterns.list",'r',encoding='utf-8') as f:
                for line in f:
                    classifierindex.add(line.strip())

            print("Loading monolithic classifier",file=sys.stderr)
            timbloptions = gettimbloptions(args, classifierconf)
            classifier = timbl.TimblClassifier(classifierdir + "/train", timbloptions)
        else:
            classifier = None

        print("Creating intermediate phrase-table",file=sys.stderr)

        #create intermediate phrasetable, with indices covering the entire test corpus instead of source text and calling classifier with context information to obtain adjusted translation with distribution
        ftable = open(classifierdir + "/phrase-table", 'w',encoding='utf-8')
        prevpattern = None
        sourcepatterncount = len(testmodel)
        for i, sourcepattern in enumerate(testmodel):
            sourcepattern_s = sourcepattern.tostring(sourcedecoders[0])
            #iterate over all occurrences, each will be encoded separately
            for sentenceindex, tokenindex in testmodel[sourcepattern]:
                #compute token span
                tokenspan = []
                for t in range(tokenindex, tokenindex + len(sourcepattern)):
                    tokenspan.append(str(sentenceindex) + "_" + str(t))
                tokenspan = " ".join(tokenspan)

                #get context configuration
                featurevector = extractcontextfeatures(classifierconf, sourcepattern, sentenceindex, tokenindex, testcorpus)
                if not featurevector:
                    raise Exception("No features returned")
                if any( [ not x for x in featurevector ] ):
                    print("ERROR: Empty feature in  " + str(sentenceindex) + ":" + str(tokenindex) + " " + sourcepattern_s + " -- Features: " + str(repr(featurevector)),file=sys.stderr)
                    raise Exception("Empty feature found in featurevector")

                translationcount = 0
                if not args.ignoreclassifier and not classifierconf['monolithic']:

                    #load classifier
                    if not prevpattern or sourcepattern != prevpattern:
                        classifierprefix = classifierdir + "/" + quote_plus(sourcepattern_s)
                        if os.path.exists(classifierprefix + ".ibase"):
                            print("Loading classifier " + classifierprefix,file=sys.stderr)
                            timbloptions = gettimbloptions(args, classifierconf)
                            classifier = timbl.TimblClassifier(classifierprefix, timbloptions)
                        elif os.path.exists(args.workdir + "/" + quote_plus(sourcepattern_s) + ".train"):
                            print("ERROR: Classifier for " + sourcepattern_s + " built but not trained!!!!",file=sys.stderr)
                            print("Classifier dir: ", classifierdir,file=sys.stderr)
                            print("Workdir (training data dir): ", args.workdir,file=sys.stderr)
                            time.sleep(1)
                        else:
                            #no classifier
                            classifier = None


                if classifier:
                    if not classifierconf['monolithic'] or (classifierconf['monolithic'] and sourcepattern_s in classifierindex):
                        print("@" + str(i+1) + "/" + str(sourcepatterncount)  + " -- Classifying " + str(sentenceindex) + ":" + str(tokenindex) + " " + sourcepattern_s + " -- Features: " + str(repr(featurevector)),file=sys.stderr)

                        #call classifier
                        classlabel, distribution, distance = classifier.classify(featurevector)

                        #process classifier result
                        for targetpattern_s, score in distribution.items():
                            if args.scorehandling == 'replace':
                                scorevector = [score]
                            else:
                                targetpattern = targetencoder.buildpattern(targetpattern_s)
                                if (sourcepattern, targetpattern) in alignmodel:
                                    scorevector = [ x for x in alignmodel[(sourcepattern,targetpattern)][0] if isinstance(x,int) or isinstance(x,float) ] #make a copy
                                else:
                                    continue

                                if args.scorehandling == 'append':
                                    scorevector.append(score)
                                elif args.scorehandling == 'weighed':
                                    raise NotImplementedError #TODO: implemented weighed!

                            translationcount += 1

                            #write phrasetable entries
                            ftable.write(tokenspan + " ||| " + targetpattern_s + " ||| " + " ".join([str(x) for x in scorevector]) + "\n")

                        if translationcount == 0:
                            print("No overlap between classifier translations (" + str(len(distribution)) + ") and phrase table. Falling back to statistical baseline.",file=sys.stderr)
                            statistical = True
                        else:
                            statistical = False
                    else:
                        print("Not in classifier. Falling back to statistical baseline.",file=sys.stderr)
                        statistical = True

                else:
                    statistical = True

                if statistical:
                    #ignore classifier or no classifier present for this item
                    for targetpattern in alignmodel.targetpatterns(sourcepattern):
                        scorevector = [ x for x in alignmodel[(sourcepattern,targetpattern)][0] if isinstance(x,int) or isinstance(x,float) ] #make a copy

                        if args.scorehandling == 'append':
                            scorevector.append(scorevector[2])
                        elif args.scorehandling == 'replace':
                            scorevector = [scorevector[2]]
                        elif args.scorehandling == 'weighed':
                            raise NotImplementedError #TODO: implemented weighed!

                        translationcount += 1

                        #write phrasetable entries
                        ftable.write(tokenspan + " ||| " + targetpattern.tostring(targetdecoder) + " ||| " + " ".join([ str(x) for x in scorevector]) + "\n")


            prevpattern = None




        ftable.close()

        if not args.tweight:
            tweights = "1\n1\n1\n1\n1\n"
            lentweights = 5
            if args.scorehandling == "append":
                tweights += "1\n"
                lentweights = 6
        else:
            tweights = "\n".join([ str(x) for x in args.tweight])
            lentweights = len(args.tweight)


        #write moses.ini
        f = open(decodedir + '/moses.ini','w',encoding='utf-8')
        f.write("""
#Moses INI, produced by contextmoses.py
[input-factors]
0

[mapping]
T 0

# translation tables: source-factors, target-factors, number of scores, file
[ttable-file]
0 0 0 {lentweights} {phrasetable}

[lmodel-file]
0 0 {lmorder} {lm}

[ttable-limit]
20

[weight-d]
{dweight}

[weight-l]
{lmweight}

[weight-t]
{tweights}

[weight-w]
{wweight}
""".format(phrasetable=classifierdir + "/phrase-table", lm=args.lm, lmorder=args.lmorder, lmweight = args.lmweight, dweight = args.dweight, tweights=tweights, lentweights=lentweights, wweight=args.wweight))
        f.close()

        if not args.skipdecoder:
            if args.mert:
                #invoke moses
                r = os.system(args.mosesdir + "/scripts/training/mert-moses.pl --mertdir=" + args.mosesdir + '/mert/' + ' ' + classifierdir + "/test.txt " + args.ref + " " + EXEC_MOSES + ' -f ' + decodedir + "/moses.ini")
            else:
                #invoke moses
                r = os.system(EXEC_MOSES + " -f " + decodedir + "/moses.ini < " + classifierdir + "/test.txt > " + decodedir + "/output.txt")


if __name__ == '__main__':
    main()
