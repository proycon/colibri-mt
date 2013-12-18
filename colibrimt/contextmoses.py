#!/usr/bin/env python

from __future__ import print_function, unicode_literals, division, absolute_import
import argparse
import sys
import os
import glob
from colibricore import IndexedCorpus, ClassEncoder, ClassDecoder, IndexedPatternModel, UnindexedPatternModel, PatternModelOptions
from colibrimt import FeaturedAlignmentModel
import timbl
import pickle

def extractcontextfeatures(classifierconf, pattern, sentence, token, factoredcorpora ):
    factorconf = classifierconf['factorconf']
    for factoredcorpus, factor in zip(factoredcorpora, factorconf):
        _,classdecoder, leftcontext, focus, rightcontext = factor
        sentencelength = factoredcorpus.sentencelength(sentence)
        for i in range(token - leftcontext,token):
            if token < 0:
                unigram = colibricore.beginpattern
            else:
                unigram = factoredcorpus[(sentence,i)]
            featurevector.append(unigram)
        if focus:
            featurevector.append(factoredcorpus[(sentence,token):(sentence,token+n)])
        for i in range(token + n , token + n + rightcontext):
            if token > sentencelength:
                unigram = colibricore.endpattern
            else:
                unigram = factoredcorpus[(sentence,i)]
            featurevector.append(unigram)
        yield featurevector




def main():
    parser = argparse.ArgumentParser(description="Wrapper around the Moses Decoder that adds support for context features through classifiers.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-f','--inputfile', type=str,help="Input text file; the test corpus (plain text, tokenised, one sentence per line), may be specified multiple times for each factor", action='append',required=False)
    parser.add_argument('-S','--sourceclassfile', type=str, help="Source class file", action='store',required=True)
    parser.add_argument('-T','--targetclassfile', type=str, help="Target class file", action='store',required=True)
    parser.add_argument('-a','--alignmodelfile', type=str,help="Colibri alignment model (made from phrase translation table)", action='store',default="",required=False)
    parser.add_argument('-w','--workdir', type=str,help="Working directory, should contain classifier training files", action='store',default="",required=True)
    parser.add_argument('--train', help="Train classifiers", action="store_true", default=False)
    parser.add_argument('-O','--timbloptions', type="str", help="Options for the Timbl classifier", action="store_true", default="-a 0 -k 1")
    parser.add_argument('-I','--ignoreclassifier', help="Ignore classifier (for testing bypass method)", action="store_true", default=False)
    args = parser.parse_args()
    #args.storeconst, args.dataset, args.num, args.bar

    if not os.path.isdir(args.workdir) or not os.path.exists(args.workdir + '/classifier.conf'):
        print("Work directory " + args.workdir + " or classifier configuration therein does not exist. Did you extract features and create classifier training files using colibri-extractfeatures?" ,file=sys.stderr)
        sys.exit(2)

    f = open(args.workdir + '/classifier.conf','rb')
    classifierconf = pickle.load(f)
    f.close()



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
            corpusfiles.append( args.workdir + "/" + os.path.basename(inputfile).replace('.txt','') + '.colibri.dat' )
            classfiles.append( args.workdir + "/" + os.path.basename(inputfile).replace('.txt','') + '.colibri.cls' )

            if os.path.exists(corpusfiles[i]) and os.path.exists(classfiles[i]):
                print("Notice: Re-using previously generated corpusfile and classfile",file=sys.stderr)
                print("Loading source class encoder and decoder",file=sys.stderr)
                sourceencoders.append( ClassEncoder(args.sourceclassfile) )
                sourcedecoders.append( ClassDecoder(args.sourceclassfile) )
            else:
                print("Loading and extending source class encoder",file=sys.stderr)
                sourceencoders.append( ClassEncoder(args.sourceclassfile) )
                sourceencoders[i].build(inputfile)
                sourceencoders[i].save(classfiles[i])
                print("Encoding test corpus",file=sys.stderr)
                sourceencoders[i].encodefile(inputfile, corpusfiles[i])
                print("Loading source class decoder",file=sys.stderr)
                sourcedecoders.append( ClassDecoder(classfiles[i]) )

            print("Loading test corpus",file=sys.stderr)
            testcorpus.append( IndexedCorpus(corpusfile[i]) )

    if not args.train and args.alignmodelfile:
        if args.inputfile:
            print("No input file specified (-f)",file=sys.stderr)
            sys.exit(2)

        print("Loading target decoder",file=sys.stderr)
        targetdecoder = ClassDecoder(args.targetclassfile)

        print("Loading alignment model (may take a while)",file=sys.stderr)
        alignmodel = FeaturedAlignmentModel()
        alignmodel.load(args.inputfile[0])

        print("Building constraint model of source patterns",file=sys.stderr)
        #constain model is needed to constrain the test model
        constraintmodel = UnindexedPatternModel()
        for pattern in alignmodel.sourcepatterns():
            constraintmodel.add(pattern)

    if args.inputfile:
        print("Building patternmodel on test corpus",file=sys.stderr)
        options = PatternModelOptions(mintokens=1)
        testmodel = IndexedPatternModel()
        testmodel.trainconstrainedbyunindexedmodel(corpusfiles[0], options, constraintmodel)
        print("Unloading constraint model",file=sys.stderr)
        del constraintmodel

    if args.train:
        #training mode
        if args.inputfile:
            print("Training classifiers (constrained by test data)",file=sys.stderr)
        else:
            print("Training all classifiers (you may want to constrain by test data using -f)",file=sys.stderr)
        for trainfile in glob.glob(args.workdir + "/*.train"):
            #build a classifier
            print("Training " + trainfile,file=sys.stderr)
            classifier = timbl.TimblClassifier(trainfile.replace('train',''), args.timbloptions)
            classifier.train()
            classifier.save()
    else:
        #TEST
        if not args.inputfile:
            print("Specify an input file (-f)",file=sys.stderr)
            sys.exit(2)



        #write intermediate test data (consisting only of indices AND unknown words) and
        f = open(args.workdir + "/test.txt",'w',encoding='utf-8')
        for sentencenum, line in enumerate(testcorpus.sentences()):
            sentenceindex = sentencenum + 1
            tokens = [] #actual string representations
            for tokenindex,pattern in enumerate(line):
                #is this an uncovered word? check using testmodel (which is constrained by alignment model source patterns)
                if not testmodel.covered( (sentenceindex, tokenindex) ):
                    tokens.append(pattern.tostring(sourcedecoder))
                else:
                    tokens.append(str(sentenceindex) + "_" + str(tokenindex))
            f.write(" ".join(tokens) + "\n")
        f.close()

        #create intermediate phrasetable, with indices covering the entire test corpus instead of source text and calling classifier with context information to obtain adjusted translation with distribution
        ftable = open(args.workdir + "/phrase-table", 'w',encoding='utf-8')
        for pattern in testmodel:
            #iterate over all occurrences, each will be encoded separately
            for sentenceindex, tokenindex in testmodel[pattern]:
                #compute token span
                tokenspan = []
                for t in range(tokenindex, tokenindex + len(pattern)):
                    tokenspan.append(str(sentenceindex) + "_" + str(t))
                tokenspan = " ".join(tokenspan)

                #get context configuration
                extractcontextfeatures(pattern, sentenceindex, tokenindex, testcorpus )



                #call classifier

                #process classifier result

                #write phrasetable entry






        ftable.close()







    #invoke moses





if __name__ == '__main__':
    main()
