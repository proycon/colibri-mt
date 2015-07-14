#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import

import argparse
import sys
import os
import glob
from colibricore import IndexedCorpus, ClassEncoder, ClassDecoder, IndexedPatternModel,  PatternModelOptions, BEGINPATTERN, ENDPATTERN #pylint: disable=import-error
from colibrimt.alignmentmodel import AlignmentModel, Configuration
import timbl
import pickle
import shutil
import subprocess
import itertools
from pynlpl.formats.moses import PhraseTable
from urllib.parse import quote_plus, unquote_plus
import xmlrpc.client
import time
import socket

def extractcontextfeatures(classifierconf, pattern, sentence, token):
    #For TEST corpus!!
    featurevector = []
    n = len(pattern)
    for configuration in classifierconf['featureconf']:
        factoredcorpus,classdecoder, leftcontext, focus, rightcontext = (configuration.corpus, configuration.classdecoder, configuration.leftcontext, configuration.focus, configuration.rightcontext)
        sentencelength = factoredcorpus.sentencelength(sentence)
        assert sentencelength > 0
        for i in range(token - leftcontext,token):
            if i < 0:
                unigram = BEGINPATTERN
            else:
                unigram = factoredcorpus[(sentence,i)]
            if len(unigram) != 1:
                raise Exception("Unigram (" + str(sentence) + "," + str(i) + "), has invalid length " + str(len(unigram)))
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
            if len(unigram) != 1:
                raise Exception("Unigram (" + str(sentence) + "," + str(i) + "), has invalid length " + str(len(unigram)))
            featurevector.append(unigram.tostring(classdecoder))
        #TODO: process keywords
    return featurevector

def gettimbloptions(args, classifierconf):
    timbloptions = "-a " + args.ta + " -k " + args.tk + " -w " + args.tw + " -m " + args.tm + " -d " + args.td  + " -vdb+s -G0"
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
    parser.add_argument('--mosesinclusive',help="Pass full sentences through through Moses server using XML input (will start a moses server, requires --moseslm). Classifier output competes with normal translation table. Score handling (-H) has no effect as only the classifier score will be passed.", action='store_true',default=False)
    parser.add_argument('--mosesexclusive',help="Pass full sentences through through Moses server using XML input (will start a moses server, requires --moseslm). Classifier does NOT compete with normal translation table. Score handling (-H) has no effect as only the classifier score will be passed.", action='store_true',default=False)
    parser.add_argument('--mosesdir', type=str,help='Path to Moses directory (required for MERT)', default="")
    parser.add_argument('--mert', type=int,help="Do MERT parameter tuning, set to number of MERT runs to perform", required=False, default=0)
    parser.add_argument('--threads', type=int, default=1, help="Number of threads to use for Moses or Mert")
    parser.add_argument('--reordering', type=str,action="store",help="Reordering type (use with --reorderingtable)", required=False)
    parser.add_argument('--reorderingtable', type=str,action="store",help="Use reordering table (use with --reordering)", required=False)
    parser.add_argument('--ref', type=str,action="store",help="Reference corpus (target corpus, plain text)", required=False)
    parser.add_argument('--lm', type=str, help="Language Model", action="store", default="", required=False)
    parser.add_argument('--lmorder', type=int, help="Language Model order", action="store", default=3, required=False)
    parser.add_argument('--lmweight', type=float, help="Language Model weight", action="store", default=0.5, required=False)
    parser.add_argument('--dweight', type=float, help="Distortion Model weight", action="store", default=0.3, required=False)
    parser.add_argument('--wweight', type=float, help="Word penalty weight", action="store", default=-1, required=False)
    parser.add_argument('--tweight', type=float, help="Translation Model weight (may be specified multiple times for each score making up the translation model)", action="append", required=False)
    parser.add_argument('--reorderingweight', type=float, help="Reordering Model weight (may be specified multiple times for each score making up the reordering model)", action="append", required=False)
    parser.add_argument('--pweight', type=float, help="Phrase penalty", default=0.2, action="store", required=False)
    parser.add_argument('--classifierdir', type=str,help="Trained classifiers, intermediate phrase-table and test file will be written here (only specify if you want a different location than the work directory)", action='store',default="",required=False)
    parser.add_argument('--decodedir', type=str,help="Moses output will be written here (only specify if you want a different location than the work directory)", action='store',default="",required=False)
    parser.add_argument('--skipdecoder',action="store_true",default=False)
    parser.add_argument('--ignoreerrors',action="store_true",help="Attempt to ignore errors",default=False)
    parser.add_argument('--mosesport',type=int, help="Port for Moses server (will be started for you), if -Z is enabled",action='store',default=8080)
    args = parser.parse_args()
    #args.storeconst, args.dataset, args.num, args.bar

    if not os.path.isdir(args.workdir) or not os.path.exists(args.workdir + '/classifier.conf'):
        print("Work directory " + args.workdir + " or classifier configuration therein does not exist. Did you extract features and create classifier training files using colibri-extractfeatures?" ,file=sys.stderr)
        sys.exit(2)

    if args.classifierdir:
        classifierdir = args.classifierdir
    else:
        classifierdir = args.workdir

    if not classifierdir:
        classifierdir = os.getcwd()
    elif classifierdir and classifierdir[0] != '/':
        classifierdir = os.getcwd() + '/' + classifierdir


    if args.mert and not args.mosesdir:
        print("--mert requires --mosesdir to be set",file=sys.stderr)
        sys.exit(2)
    if args.mert and not args.ref:
        print("--mert requires --ref to be set",file=sys.stderr)
        sys.exit(2)

    if args.decodedir:
        decodedir = args.decodedir
    else:
        decodedir = args.workdir

    if not decodedir:
        decodedir = os.getcwd()
    elif decodedir and decodedir[0] != '/':
        decodedir = os.getcwd() + '/' + decodedir

    print("Loading configuration (training corpora and class decoders)",file=sys.stderr)
    f = open(args.workdir + '/classifier.conf','rb')
    classifierconf = pickle.load(f)
    f.close()

    print("Configuration: ", classifierconf,file=sys.stderr)


    if args.inputfile:
        if len(classifierconf['featureconf']) > len(args.inputfile):
            raise Exception("Number of input files (" + str(len(args.inputfile)) + ") is less than the number of factor-features in configuration (" + str(len(classifierconf['featureconf'])) + "), you need to specify all")


    #one for each factor
    sourceencoders = []



    if args.inputfile:
        l = []
        for i, (inputfile, conf) in enumerate(zip(args.inputfile, classifierconf['featureconf'])):
            trainclassfile = conf['classdecoder']
            print("Processing factor #" + str(i),file=sys.stderr)
            #process inputfile
            corpusfile =   os.path.basename(inputfile).replace('.txt','') + '.colibri.dat'
            classfile = os.path.basename(inputfile).replace('.txt','') + '.colibri.cls'

            #if os.path.exists(corpusfiles[i]) and os.path.exists(classfiles[i]):
            #    print("Notice: Re-using previously generated corpusfile and classfile",file=sys.stderr)
            #    print("Loading source class encoder and decoder",file=sys.stderr)
            #    sourceencoders.append( ClassEncoder(classfiles[i]) )
            #    sourcedecoders.append( ClassDecoder(classfiles[i]) )
            #else:
            print("Loading and extending source class encoder, from " + trainclassfile + " to " + classfile,file=sys.stderr)
            sourceencoders.append( ClassEncoder(trainclassfile) )
            sourceencoders[i].build(inputfile)
            sourceencoders[i].save(classfile)
            print("Encoding test corpus, from " + inputfile + " to " + corpusfile,file=sys.stderr)
            sourceencoders[i].encodefile(inputfile, corpusfile)
            print("Loading source class decoder " + classfile,file=sys.stderr)
            sourcedecoder = ClassDecoder(classfile)

            print("Loading test corpus " + corpusfile,file=sys.stderr)

            l.append( Configuration( IndexedCorpus(corpusfile), sourcedecoder, conf['leftcontext'], conf['focus'], conf['rightcontext']) )

        classifierconf['featureconf'] = l

    else:
        print("Loading source class decoders",file=sys.stderr)
        l = []
        for conf in classifierconf['featureconf']:
            sourcedecoder = ClassDecoder(conf['classdecoder'])
            l.append( Configuration( IndexedCorpus(), sourcedecoder, conf['leftcontext'], conf['focus'], conf['rightcontext'] ) )



    if args.inputfile and args.alignmodelfile:

        print("Loading target encoder " + args.targetclassfile,file=sys.stderr)
        targetencoder = ClassEncoder(args.targetclassfile)
        print("Loading target decoder " + args.targetclassfile,file=sys.stderr)
        targetdecoder = ClassDecoder(args.targetclassfile)

        print("Loading alignment model " + args.alignmodelfile ,file=sys.stderr)
        alignmodel = AlignmentModel(args.alignmodelfile)
        print("\tAlignment model has " + str(len(alignmodel)) + " source patterns",file=sys.stderr)


        print("Building patternmodel on test corpus " + classifierconf['featureconf'][0].corpus.filename() ,file=sys.stderr)
        options = PatternModelOptions(mintokens=1, maxlength=12)
        testmodel = IndexedPatternModel()
        testmodel.train( classifierconf['featureconf'][0].corpus.filename(), options, alignmodel)
        print("\tTest model has " + str(len(testmodel)) + " source patterns",file=sys.stderr)

        #saving just so we can inspect it for debug purposes:
        testmodel.write(  decodedir + '/test.colibri.indexedpatternmodel'  )


        if args.reorderingtable:
            print("Loading reordering model (may take a while)",file=sys.stderr)
            rtable = PhraseTable(args.reorderingtable) #TODO: convert to colibri alignmodel



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
            for trainfile in itertools.chain(glob.glob(args.workdir + "/*.train"), glob.glob(args.workdir + "/.*.train")): #explicitly add 'dotfiles', will be skipped by default
                if args.inputfile:
                    sourcepattern_s = unquote_plus(os.path.basename(trainfile.replace('.train','')))
                    sourcepattern = sourceencoders[0].buildpattern(sourcepattern_s)
                    if not sourcepattern in testmodel:
                        if sourcepattern_s == "一 杯 咖啡 。":
                            import pdb; pdb.set_trace()
                        print("Skipping " + trainfile + " (\"" + sourcepattern_s + "\" not in test model)",file=sys.stderr)
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
                if not os.path.exists(trainfile.replace(".train",".ibase")):
                    raise Exception("Resulting instance base " + trainfile.replace(".train",".ibase") + " not found!")
    else:
        #TEST
        if not args.inputfile:
            print("Specify an input file (-f)",file=sys.stderr)
            sys.exit(2)


        if not args.mosesinclusive and not args.mosesexclusive:
            print("Writing intermediate test data to " + decodedir + "/test.txt",file=sys.stderr)
            #write intermediate test data (consisting only of indices AND unknown words) and
            f = open(decodedir + "/test.txt",'w',encoding='utf-8')
            for sentencenum, line in enumerate(classifierconf['featureconf'][0].corpus.sentences()):
                sentenceindex = sentencenum + 1
                print("@" + str(sentenceindex),file=sys.stderr)
                tokens = [] #actual string representations
                for tokenindex,pattern in enumerate(line): #will yield only unigrams
                    #is this an uncovered word that does not appear in the phrasetable? check using alignment model and keep the word untranslated if so
                    if not pattern in alignmodel:
                        print("     Found OOV at @" + str(sentenceindex) + ":" + str(tokenindex) + ": " + pattern.tostring(classifierconf['featureconf'][0].classdecoder), file=sys.stderr)
                        tokens.append(pattern.tostring(classifierconf['featureconf'][0].classdecoder))
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

            print("Loading monolithic classifier " + classifierdir + "/train.train",file=sys.stderr)
            timbloptions = gettimbloptions(args, classifierconf)
            classifier = timbl.TimblClassifier(classifierdir + "/train", timbloptions)
        else:
            classifier = None

        if args.reorderingtable:
            print("Creating intermediate phrase-table and reordering-table",file=sys.stderr)
            freordering = open(decodedir + "/reordering-table", 'w',encoding='utf-8')
        else:
            print("Creating intermediate phrase-table",file=sys.stderr)
            freordering = None

        if args.mosesinclusive or args.mosesexclusive:
            #Use mosesserver with XML input method

            #write mos
            if not args.tweight:
                lentweights = 4
                tweights = " ".join([str(1/(lentweights+1))]*lentweights)
            else:
                tweights = " ".join([ str(x) for x in args.tweight])
                lentweights = len(args.tweight)


            if os.path.exists(decodedir + "/moses.ini"):
                os.unlink(decodedir+"/moses.ini")

            print("Writing " + decodedir + "/moses.ini",file=sys.stderr)


            if args.reordering:
                reorderingfeature = "LexicalReordering name=LexicalReordering0 num-features=6 type=" + args.reordering + " input-factor=0 output-factor=0 path=" + decodedir + "/reordering-table"
                reorderingweight =  "LexicalReordering0= 0.3 0.3 0.3 0.3 0.3 0.3"
            else:
                reorderingfeature = ""
                reorderingweight = ""

            #write moses.ini
            f = open(decodedir + '/moses.ini','w',encoding='utf-8')
            f.write("""
#Moses INI, produced by contextmoses.py
[input-factors]
0

[mapping]
0 T 0

[distortion-limit]
6

[feature]
UnknownWordPenalty
WordPenalty
PhrasePenalty
PhraseDictionaryMemory name=TranslationModel0 num-features={lentweights} path={phrasetable} input-factor=0 output-factor=0 table-limit=20
{reorderingfeature}
Distortion
SRILM name=LM0 factor=0 path={lm} order={lmorder}

[weight]
UnknownWordPenalty0= 1
WordPenalty0= {wweight}
PhrasePenalty0= {pweight}
LM0= {lmweight}
TranslationModel0= {tweights}
Distortion0= {dweight}
{reorderingweight}
""".format(phrasetable=decodedir + "/phrase-table", lm=args.lm, lmorder=args.lmorder, lmweight = args.lmweight, dweight = args.dweight, tweights=tweights, lentweights=lentweights, wweight=args.wweight, pweight = args.pweight, reorderingfeature=reorderingfeature, reorderingweight=reorderingweight))
            f.close()

            print("Starting Moses Server",file=sys.stderr)
            if args.mosesdir:
                cmd = args.mosesdir + '/bin/mosesserver'
            else:
                cmd = 'mosesserver'
            if args.moses:
                if args.mosesinclusive:
                    cmd += " -xml-input inclusive" #compete with phrase-table
                elif args.mosesexclusive:
                    cmd += " -xml-input exclusive" #only used for passing verbatim L2 (tested whether it makes a difference with inclusive baseline on en-es data, it doesn't)
            cmd += ' -f ' + decodedir + '/moses.ini'
            print("Calling mosesserver: " + cmd,file=sys.stderr)

            p = subprocess.Popen(cmd,shell=True)
            mosesserverpid = p.pid

            while True:
                time.sleep(5)
                try:
                    s = socket.socket()
                    s.connect( ("localhost", args.mosesport) )
                    break
                except Exception as e:
                    print("Waiting for Moses server....", e, file=sys.stderr)

            print("Connecting to Moses Server",file=sys.stderr)
            mosesclient = xmlrpc.client.ServerProxy("http://localhost:" + str(args.mosesport) + "/RPC2")

        else: #No XML method

            #create intermediate phrasetable, with indices covering the entire test corpus instead of source text and calling classifier with context information to obtain adjusted translation with distribution
            ftable = open(decodedir + "/phrase-table", 'w',encoding='utf-8')
            prevpattern = None
            sourcepatterncount = len(testmodel)
            for i, sourcepattern in enumerate(testmodel):
                sourcepattern_s = sourcepattern.tostring(classifierconf['featureconf'][0].classdecoder)
                #iterate over all occurrences, each will be encoded separately
                for sentenceindex, tokenindex in testmodel[sourcepattern]:
                    #compute token span
                    tokenspan = []
                    for t in range(tokenindex, tokenindex + len(sourcepattern)):
                        tokenspan.append(str(sentenceindex) + "_" + str(t))
                    tokenspan = " ".join(tokenspan)

                    #get context configuration
                    featurevector = extractcontextfeatures(classifierconf, sourcepattern, sentenceindex, tokenindex) #testcorpus is passed as part of classifierconf['featureconf']
                    if not featurevector:
                        raise Exception("No features returned")
                    if any( [ not x for x in featurevector ] ):
                        print("ERROR: Empty feature in  " + str(sentenceindex) + ":" + str(tokenindex) + " " + sourcepattern_s + " -- Features: " + str(repr(featurevector)),file=sys.stderr)
                        raise Exception("Empty feature found in featurevector")

                    translationcount = 0
                    if not args.ignoreclassifier and not classifierconf['monolithic']:

                        #load classifier
                        if not prevpattern or sourcepattern_s != prevpattern:
                            classifierprefix = classifierdir + "/" + quote_plus(sourcepattern_s)
                            trainfile = args.workdir + "/" + quote_plus(sourcepattern_s) + ".train"
                            ibasefile = classifierprefix + ".ibase"
                            if os.path.exists(ibasefile):
                                print("Loading classifier " + classifierprefix + " for " + sourcepattern_s,file=sys.stderr)
                                timbloptions = gettimbloptions(args, classifierconf)
                                classifier = timbl.TimblClassifier(classifierprefix, timbloptions)
                            elif os.path.exists(trainfile):
                                print("ERROR: Classifier for " + sourcepattern_s + " built but not trained!!!! " + trainfile + " exists but " + ibasefile + " misses",file=sys.stderr)
                                print("Classifier dir: ", classifierdir,file=sys.stderr)
                                print("Workdir (training data dir): ", args.workdir,file=sys.stderr)
                                raise Exception("ERROR: Classifier for " + sourcepattern_s + " built but not trained!!!!")
                            else:
                                #no classifier
                                classifier = None
                            prevpattern = sourcepattern_s


                    print("@" + str(i+1) + "/" + str(sourcepatterncount)  + " -- Processing " + str(sentenceindex) + ":" + str(tokenindex) + " " + sourcepattern_s + " -- Features: " + str(repr(featurevector)),file=sys.stderr)

                    if classifier and not args.ignoreclassifier:
                        if not classifierconf['monolithic'] or (classifierconf['monolithic'] and sourcepattern_s in classifierindex):
                            print("\tClassifying",file=sys.stderr)

                            #call classifier
                            classlabel, distribution, distance = classifier.classify(featurevector)

                            #process classifier result
                            for targetpattern_s, score in distribution.items():
                                targetpattern = targetencoder.buildpattern(targetpattern_s)
                                if (sourcepattern, targetpattern) in alignmodel:
                                    scorevector = [ x for x in alignmodel[(sourcepattern,targetpattern)] if isinstance(x,int) or isinstance(x,float) ] #make a copy
                                else:
                                    continue

                                if args.scorehandling == 'append':
                                    scorevector.append(score)
                                elif args.scorehandling == 'replace':
                                    scorevector[2] = score
                                else:
                                    raise NotImplementedError #TODO: implemented weighed!

                                translationcount += 1

                                #write phrasetable entries
                                ftable.write(tokenspan + " ||| " + targetpattern_s + " ||| " + " ".join([str(x) for x in scorevector]) + "\n")
                                if freordering:
                                    reordering_scores = None
                                    try:
                                        for t, sv in rtable[sourcepattern_s]:
                                            if t == targetpattern_s:
                                                reordering_scores = sv
                                    except KeyError:
                                        if args.ignoreerrors:
                                            print("******* ERROR ********* Source pattern notfound in reordering table: " + sourcepattern_s,file=sys.stderr)
                                            continue
                                        else:
                                            raise Exception("Source pattern notfound in reordering table: " + sourcepattern_s)

                                    if reordering_scores:
                                        freordering.write(tokenspan + " ||| " + targetpattern_s + " ||| " + " ".join([str(x) for x in reordering_scores]) + "\n")
                                    else:
                                        if args.ignoreerrors:
                                            print("******** ERROR ********* Target pattern not found in reordering table: " + targetpattern_s + " (for source " + sourcepattern_s + ")",file=sys.stderr)
                                            continue
                                        else:
                                            raise Exception("Target pattern not found in reordering table: " + targetpattern_s + " (for source " + sourcepattern_s + ")")

                            if translationcount == 0:
                                print("\tNo overlap between classifier translations (" + str(len(distribution)) + ") and phrase table. Falling back to statistical baseline.",file=sys.stderr)
                                statistical = True
                            else:
                                print("\t\t" + str(translationcount) + " translation options written",file=sys.stderr)
                                statistical = False
                        else:
                            print("\tNot in classifier. Falling back to statistical baseline.",file=sys.stderr)
                            statistical = True

                    else:
                        statistical = True

                    if statistical:
                        print("\tPhrasetable lookup",file=sys.stderr)
                        #ignore classifier or no classifier present for this item
                        for targetpattern in alignmodel.targetpatterns(sourcepattern):
                            scorevector = [ x for x in alignmodel[(sourcepattern,targetpattern)] if isinstance(x,int) or isinstance(x,float) ] #make a copy

                            if args.scorehandling == 'append':
                                scorevector.append(scorevector[2])
                            elif args.scorehandling == 'replace':
                                pass #nothing to do, scorevector is okay as it is
                            elif args.scorehandling == 'weighed':
                                raise NotImplementedError #TODO: implemented weighed!

                            translationcount += 1

                            #write phrasetable entries
                            targetpattern_s = targetpattern.tostring(targetdecoder)
                            ftable.write(tokenspan + " ||| " + targetpattern_s + " ||| " + " ".join([ str(x) for x in scorevector]) + "\n")
                            if freordering:
                                reordering_scores = None
                                try:
                                    for t, sv in rtable[sourcepattern_s]:
                                        if t == targetpattern_s:
                                            reordering_scores = sv
                                except KeyError:
                                    if args.ignoreerrors:
                                        print("******** ERROR ******* Source pattern not found in reordering table: " + sourcepattern_s,file=sys.stderr)
                                        continue
                                    else:
                                        raise Exception("Source pattern not found in reordering table: " + sourcepattern_s)

                                if reordering_scores:
                                    freordering.write(tokenspan + " ||| " + targetpattern_s + " ||| " + " ".join([str(x) for x in reordering_scores]) + "\n")
                                else:
                                    if args.ignoreerrors:
                                            print("******* ERROR ****** Target pattern not found in reordering table: " + targetpattern_s + " (for source " + sourcepattern_s + ")",file=sys.stderr)
                                            continue
                                    else:
                                        raise Exception("Target pattern not found in reordering table: " + targetpattern_s + " (for source " + sourcepattern_s + ")")

                        print("\t\t" + str(translationcount) + " translation options written",file=sys.stderr)


                prevpattern = None




            ftable.close()
            if freordering:
                freordering.close()

            if not args.tweight:
                if args.scorehandling == "append":
                    lentweights = 5
                else:
                    lentweights = 4
                tweights = " ".join([str(1/(lentweights+1))]*lentweights)
            else:
                tweights = " ".join([ str(x) for x in args.tweight])
                lentweights = len(args.tweight)


            print("Writing " + decodedir + "/moses.ini",file=sys.stderr)

            if args.reordering:
                reorderingfeature = "LexicalReordering name=LexicalReordering0 num-features=6 type=" + args.reordering + " input-factor=0 output-factor=0 path=" + decodedir + "/reordering-table"
                if not args.reorderingweight:
                    reorderingweight =  "LexicalReordering0= 0.3 0.3 0.3 0.3 0.3 0.3"
                else:
                    reorderingweight =  "LexicalReordering0= " + " ".join([str(x) for x in args.reorderingweight])
            else:
                reorderingfeature = ""
                reorderingweight = ""

            #write moses.ini
            f = open(decodedir + '/moses.ini','w',encoding='utf-8')
            f.write("""
#Moses INI, produced by contextmoses.py
[input-factors]
0

[mapping]
0 T 0

[distortion-limit]
6

[feature]
UnknownWordPenalty
WordPenalty
PhrasePenalty
PhraseDictionaryMemory name=TranslationModel0 num-features={lentweights} path={phrasetable} input-factor=0 output-factor=0 table-limit=20
{reorderingfeature}
Distortion
SRILM name=LM0 factor=0 path={lm} order={lmorder}

[weight]
UnknownWordPenalty0= 1
WordPenalty0= {wweight}
PhrasePenalty0= {pweight}
LM0= {lmweight}
TranslationModel0= {tweights}
Distortion0= {dweight}
{reorderingweight}
""".format(phrasetable=decodedir + "/phrase-table", lm=args.lm, lmorder=args.lmorder, lmweight = args.lmweight, dweight = args.dweight, tweights=tweights, lentweights=lentweights, wweight=args.wweight, pweight = args.pweight, reorderingfeature=reorderingfeature, reorderingweight=reorderingweight))



            f.close()

            if not args.skipdecoder:
                if args.mert:
                    if args.ref[0] == '/':
                        ref = args.ref
                    else:
                        ref = os.getcwd() + '/' + args.ref

                    for mertrun in range(1,args.mert+1):
                        if os.path.exists(decodedir+"/mert-work-" + str(mertrun) +"/moses.ini"):
                            print("Mert run #" + str(mertrun) + " already ran, skipping...",file=sys.stderr)
                        else:
                            #invoke mert
                            cmd = args.mosesdir + "/scripts/training/mert-moses.pl --working-dir=" + decodedir + "/mert-work-" + str(mertrun) + " --mertdir=" + args.mosesdir + '/mert/' + ' --decoder-flags="-threads ' + str(args.threads) + '" ' + decodedir + "/test.txt " + ref + " `which moses` " + decodedir + "/moses.ini --threads=" + str(args.threads)
                            print("Contextmoses calling mert #" + str(mertrun) + ": " + cmd,file=sys.stderr)
                            r = subprocess.call(cmd, shell=True)
                            if r != 0:
                                print("Contextmoses called mert #" + str(mertrun) + " but failed!", file=sys.stderr)
                                sys.exit(1)
                            print("DONE: Contextmoses calling mert #" + str(mertrun)+": " + cmd,file=sys.stderr)
                else:
                    #invoke moses
                    cmd = EXEC_MOSES + " -threads " + str(args.threads) + " -f " + decodedir + "/moses.ini < " + decodedir + "/test.txt > " + decodedir + "/output.txt"
                    print("Contextmoses calling moses: " + cmd,file=sys.stderr)
                    r = subprocess.call(cmd, shell=True)
                    if r != 0:
                        print("Contextmoses called moses but failed!", file=sys.stderr)
                        sys.exit(1)
                    print("DONE: Contextmoses calling moses: " + cmd,file=sys.stderr)

            else:
                print("Contextmoses skipping decoder",file=sys.stderr)


if __name__ == '__main__':
    main()
