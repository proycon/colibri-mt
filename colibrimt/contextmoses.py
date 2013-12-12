#!/usr/bin/env python

from __future__ import print_function, unicode_literals, division, absolute_import
import argparse
import sys
import os
import glob
from colibricore import IndexedCorpus, ClassEncoder, ClassDecoder, IndexedPatternModel, UnindexedPatternModel, PatternModelOptions
from colibrimt import FeaturedAlignmentModel
import timbl

def main():
    parser = argparse.ArgumentParser(description="Wrapper around the Moses Decoder that adds support for context features through classifiers.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-f','--inputfile', type=str,help="Input text file; the test corpus (plain text, tokenised, one sentence per line)", action='store',default="",required=False)
    parser.add_argument('-S','--sourceclassfile', type=str, help="Source class file", action='store',required=True)
    parser.add_argument('-T','--targetclassfile', type=str, help="Target class file", action='store',required=True)
    parser.add_argument('-a','--alignmodelfile', type=str,help="Colibri alignment model (made from phrase translation table)", action='store',default="",required=False)
    parser.add_argument('-w','--workdir', type=str,help="Working directory, should contain classifier training files", action='store',default="",required=True)
    parser.add_argument('--train', help="Train classifiers", action="store_true", default=False)
    parser.add_argument('-O','--timbloptions', type="str", help="Options for the Timbl classifier", action="store_true", default="-a 0 -k 1")
    parser.add_argument('-I','--ignoreclassifier', help="Ignore classifier (for testing bypass method)", action="store_true", default=False)
    args = parser.parse_args()
    #args.storeconst, args.dataset, args.num, args.bar

    if not os.path.isdir(args.workdir):
        print("Work directory " + args.workdir + " does not exist. Did you extract features and create classifier training files using colibri-extractfeatures?" ,file=sys.stderr)
        sys.exit(2)



    if args.inputfile:
        #process inputfile
        corpusfile = args.workdir + "/" + os.path.basename(args.inputfile).replace('.txt','') + '.colibri.dat'
        classfile = args.workdir + "/" + os.path.basename(args.inputfile).replace('.txt','') + '.colibri.cls'

        if os.path.exists(corpusfile) and os.path.exists(classfile):
            print("Notice: Re-using previously generated corpusfile and classfile",file=sys.stderr)
            print("Loading source class encoder and decoder",file=sys.stderr)
            sourceencoder = ClassEncoder(args.sourceclassfile)
            sourcedecoder = ClassDecoder(args.sourceclassfile)
        else:
            print("Loading and extending source class encoder",file=sys.stderr)
            sourceencoder = ClassEncoder(args.sourceclassfile)
            sourceencoder.build(args.inputfile)
            sourceencoder.save(classfile)
            print("Encoding test corpus",file=sys.stderr)
            sourceencoder.encodefile(args.inputfile, corpusfile)
            print("Loading source class decoder",file=sys.stderr)
            sourcedecoder = ClassDecoder(classfile)

        print("Loading test corpus",file=sys.stderr)
        testcorpus = IndexedCorpus(corpusfile)

    if args.alignmodelfile:
        print("Loading target decoder",file=sys.stderr)
        targetdecoder = ClassDecoder(args.targetclassfile)
        print("Loading alignment model (may take a while)",file=sys.stderr)
        alignmodel = FeaturedAlignmentModel()
        alignmodel.load(args.inputfile)

        if args.inputfile:
            print("Building constraint model of source patterns",file=sys.stderr)
            #constain model is needed to constrain the test model
            constraintmodel = UnindexedPatternModel()
            for pattern in alignmodel.sourcepatterns():
                constraintmodel.add(pattern)

    if args.inputfile:
        print("Building patternmodel on test corpus",file=sys.stderr)
        options = PatternModelOptions(mintokens=1)
        testmodel = UnindexedPatternModel()
        testmodel.trainconstrainedbyunindexedmodel(corpusfile, options, constraintmodel)
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
        if not args.inputfile:
            print("Specify an input file (-f)",file=sys.stderr)
            sys.exit(2)



if __name__ == '__main__':
    main()
