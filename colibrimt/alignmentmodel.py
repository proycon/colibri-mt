#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import

import sys
import datetime
import bz2
import gzip
import colibricore
import argparse
import pickle
import os
from collections import defaultdict
from urllib.parse import quote_plus


class Configuration:
    def __init__(self, corpus, classdecoder, leftcontext, rightcontext, focus=True):
        assert isinstance(corpus, colibricore.IndexedCorpus)
        assert isinstance(classdecoder, colibricore.ClassDecoder)
        assert isinstance(leftcontext, int)
        assert isinstance(rightcontext, int)
        self.corpus = corpus
        self.classdecoder = classdecoder
        self.leftcontext = leftcontext
        self.focus = focus
        self.rightcontext = rightcontext



class AlignmentModel(colibricore.PatternAlignmentModel_float):
    def sourcepatterns(self):
        for sourcepattern in self:
            yield sourcepattern


    def targetpatterns(self, sourcepattern=None):
        if sourcepattern is None:
            s = colibricore.PatternSet() #//segfaults (after 130000+ entries)? can't figure out why yet
            #s = set()
            for sourcepattern, targetmap in self.items():
                for targetpattern in targetmap:
                    s.add(targetpattern)

            for targetpattern in s:
                yield targetpattern
        else:
            for targetpattern in self[sourcepattern]:
                yield targetpattern

    def itemcount(self):
        count = 0
        for _ in self.items():
            count += 1
        return count


    #NOTE: triples() replaces what used to be items()

    def output(self, sourcedecoder, targetdecoder, scorefilter=None):
        for sourcepattern, targetpattern, features in self.triples():
            if scorefilter and not scorefilter(features): continue
            print(sourcepattern.tostring(sourcedecoder) + "\t" + targetpattern.tostring(targetdecoder) + "\t" + "\t".join([str(x) for x in features]))

    def sourcemodel(self):
        model = colibricore.UnindexedPatternModel()
        for sourcepattern in self.sourcepatterns():
            model[sourcepattern] = model[sourcepattern] + 1
        return model

    def targetmodel(self):
        model = colibricore.UnindexedPatternModel()
        for targetpattern in self.targetpatterns():
            model[targetpattern] = model[targetpattern] + 1
        return model

    #TODO: probably need reimplementation
    def _normaux(self, sourcepattern, targetpattern, total_s, total_t, value, index, sumover):
        if sumover == 's':
            total_s[sourcepattern] += value[index]
        elif sumover == 't':
            total_t[targetpattern] += value[index]
        else:
            raise Exception("sumover can't be " + sumover)


    def __init__(self, filename=None):
        if filename:
            self.load(filename)


    def load(self, filename, options=None):
        if not options:
            options = colibricore.PatternModelOptions()
        if os.path.exists(filename):
            super().load(filename, options)
        else:
            raise IOError("File not found: " + filename)

    def save(self, filename):
        super().write(filename)




    def savemosesphrasetable(self, filename, sourcedecoder, targetdecoder):
        """Output for moses"""
        with open(filename,'w',encoding='utf-8') as f:
            for sourcepattern, targetpattern, features in self.triples():
                f.write(sourcepattern.tostring(sourcedecoder) + " ||| " + targetpattern.tostring(targetdecoder) + " ||| ")
                for i, feature in enumerate(features):
                    if (i > 0): f.write(" ")
                    f.write(str(feature))
                f.write("\n")

    def loadmosesphrasetable(self, filename, sourceencoder, targetencoder,constrainsourcemodel=None,constraintargetmodel=None, quiet=False, reverse=False, delimiter="|||", score_column = 3, max_sourcen = 0, scorefilter = lambda x:True, divergencefrombestthreshold=0.0, divfrombestindex=2):
        """Load a phrase table from file into memory (memory intensive!)"""

        if filename.split(".")[-1] == "bz2":
            f = bz2.BZ2File(filename,'r')
        elif filename.split(".")[-1] == "gz":
            f = gzip.GzipFile(filename,'r')
        else:
            f = open(filename,'r',encoding='utf-8')
        linenum = 0
        source = None
        prevsource = None

        added = 0
        skipped = 0
        constrained = 0


        buffer = []

        while True:

            if not quiet:
                linenum += 1
                if (linenum % 100000) == 0:
                    s = ""
                    if constrainsourcemodel or constraintargetmodel:
                        s = ", skipped because of constraint model: " + str(constrained)
                    print("Loading phrase-table: @" + str(linenum) + "\t(" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ") total added: " + str(added) + ", skipped because of threshold: " + str(skipped) + s,file=sys.stderr)
            line = f.readline()
            if not line:
                break
            if filename.split(".")[-1] == "bz2" or filename.split(".")[-1] == "gz":
                line = str(line,'utf-8')

            #split into (trimmed) segments
            segments = [ segment.strip() for segment in line.split(delimiter) ]

            if len(segments) < 3:
                print("Invalid line: ", line, file=sys.stderr)
                continue


            #Do we have a score associated?
            if score_column > 0 and len(segments) >= score_column:
                scores = [ float(x) for x in segments[score_column-1].strip().split()  ]
            else:
                scores = []


            #if align2_column > 0:
            #    try:
            #        null_alignments = segments[align2_column].count("()")
            #    except:
            #        null_alignments = 0
            #else:
            #    null_alignments = 0

            if scorefilter and not scorefilter(scores):
                print("SKIPPED: ", scores,file=sys.stderr)
                skipped += 1
                continue


            #disable wordalignments

            #if len(segments) >= 4:
            #    scores.append( [ tuple([int(y) for y in x.split('-')]) for x in segments[3].split() ] )
            #    haswordalignments = True
            #elif haswordalignments:
            #    scores.append([])


            if reverse:
                if max_sourcen > 0 and segments[1].count(' ') + 1 > max_sourcen:
                    skipped += 1
                    continue

                source = sourceencoder.buildpattern(segments[1]) #tuple(segments[1].split(" "))
                target = targetencoder.buildpattern(segments[0]) #tuple(segments[0].split(" "))
            else:
                if max_sourcen > 0 and segments[0].count(' ') + 1 > max_sourcen:
                    skipped += 1
                    continue

                source = sourceencoder.buildpattern(segments[0]) #tuple(segments[0].split(" "))
                target = targetencoder.buildpattern(segments[1]) #tuple(segments[1].split(" "))

            if buffer and source != prevsource:
                bestscore = 0
                if divergencefrombestthreshold > 0:
                    for item in buffer:
                        source_buffer,target_buffer, scores_buffer = item
                        if scores_buffer[divfrombestindex] > bestscore:
                            bestscore = scores_buffer[divfrombestindex]

                for item in buffer:
                    source_buffer,target_buffer, scores_buffer = item
                    if scores_buffer[divfrombestindex] >= bestscore * divergencefrombestthreshold:
                        added += 1
                        self.add(source_buffer,target_buffer, tuple(scores_buffer))
                    else:
                        skipped += 1

                buffer = []

            if constrainsourcemodel and source not in constrainsourcemodel:
                constrained += 1
                continue
            if constraintargetmodel and target not in constraintargetmodel:
                constrained += 1
                continue


            buffer.append( ( source,target, scores) )
            prevsource = source


        f.close()

        #don't forget last item
        if buffer and source != prevsource:
            bestscore = 0
            if divergencefrombestthreshold > 0:
                for item in buffer:
                    source,target, scores = item
                    if scores[divfrombestindex] > bestscore:
                        bestscore = scores[divfrombestindex]

            for item in buffer:
                added += 1
                source,target, scores = item
                if bestscore * divergencefrombestthreshold >= scores[divfrombestindex]:
                    self.add( ( source,target, scores) )
                    added += 1
                else:
                    skipped += 1




    def patternswithindexes(self, sourcemodel, targetmodel, showprogress=True):
        """Finds occurrences (positions in the source and target models) for all patterns in the alignment model. """
        l = len(self)
        for i, sourcepattern in enumerate(self.sourcepatterns()):
            if showprogress:
                print("@" + str(i+1) + "/" + str(l), " " , round(((i+1)/l)*100,2),'%', file=sys.stderr)
            occurrences = 0
            if not sourcepattern in sourcemodel:
                continue

            tmpdata = defaultdict(list)

            sourceindexes = None #loading deferred until really needed
            for targetpattern in self.targetpatterns(sourcepattern):
                #print("DEBUG targetpattern=", sourcepattern,file=sys.stderr)
                if not targetpattern in targetmodel:
                    continue

                if not sourceindexes: #loading deferred until here to improve performance, preventing unnecessary loads
                    sourceindexes = defaultdict(list)
                    for sourcesentence, sourcetoken in sourcemodel[sourcepattern]:
                        sourceindexes[sourcesentence].append(sourcetoken)

                targetindexes = defaultdict(list)
                for targetsentence, targettoken in targetmodel[targetpattern]:
                    if targetsentence in sourceindexes:
                        targetindexes[targetsentence].append(targettoken)

                ptsscore = self[(sourcepattern,targetpattern)][2] #assuming moses style score vector!

                #for every occurrence of this pattern in the source
                for sentence in targetindexes:
                    #print("DEBUG sourceindex=", (sentence,token),file=sys.stderr)
                    #is a target pattern found in the same sentence? (if so we *assume* they're aligned, we don't actually use the word alignments anymore here)
                    for token in sourceindexes[sentence]:
                        for targettoken in targetindexes[sentence]:
                            tmpdata[(sentence,token,targettoken)].append( (ptsscore, sourcepattern, targetpattern) )
                            #yield sourcepattern, targetpattern, sentence, token, sentence, targettoken
                            break #multiple possible matches in same sentence? just pick first one... no word alignments here to resolve this

            #make sure only the strongest targetpattern for a given occurrence is chosen, in case multiple options exist
            for (sentence,token, targettoken),targets  in tmpdata.items():
                ptsscore,sourcepattern, targetpattern = sorted(targets)[-1] #sorted by ptsscore, last item will be highest
                occurrences += 1
                yield sourcepattern, targetpattern, sentence, token, sentence, targettoken

            if showprogress:
                print("\tFound " + str(occurrences) + " occurrences", file=sys.stderr)


    def extractcontextfeatures(self, sourcemodel, targetmodel, configurations, crosslingual=False):
        featurevector = []
        assert isinstance(sourcemodel, colibricore.IndexedPatternModel)
        assert isinstance(targetmodel, colibricore.IndexedPatternModel)
        assert isinstance(configurations, list) or isinstance(configurations, tuple)
        assert all([ isinstance(x, Configuration) for x in configurations ])


        prev = None
        tmpdata = defaultdict(int) # featurevector => occurrencecount


        count = 0

        extracted = 0
        for data in self.patternswithindexes(sourcemodel, targetmodel):
            if crosslingual:
                #we're interested in the target-side sentence and token
                sourcepattern, targetpattern, _,_, sentence,token  = data
            else:
                #normal behaviour
                sourcepattern, targetpattern, sentence, token,_,_  = data
            count+=1
            n = len(sourcepattern)

            if (sourcepattern, targetpattern) != prev:
                if prev:
                    #process previous
                    allfeaturevectors = []
                    scorevector = self[prev]

                    for featurevector, count in tmpdata.items():
                        allfeaturevectors.append( (featurevector, count) )

                    yield prev[0], prev[1], allfeaturevectors, scorevector

                tmpdata = defaultdict(int) #reset
                prev = (sourcepattern,targetpattern)

            featurevector = [] #local context features

            for configuration in configurations:
                factoredcorpus,classdecoder, leftcontext, focus, rightcontext = (configuration.corpus, configuration.classdecoder, configuration.leftcontext, configuration.focus, configuration.rightcontext)
                sentencelength = factoredcorpus.sentencelength(sentence)
                for i in range(token - leftcontext,token):
                    if i < 0:
                        unigram = colibricore.BEGINPATTERN
                    else:
                        unigram = factoredcorpus[(sentence,i)]
                    assert len(unigram) == 1
                    featurevector.append(unigram)
                if focus: #focus needs a different class decoder if run with crosslingual! will be handled by featurestostring()
                    featurevector.append(sourcepattern)
                for i in range(token + n , token + n + rightcontext):
                    if i >= sentencelength:
                        unigram = colibricore.ENDPATTERN
                    else:
                        unigram = factoredcorpus[(sentence,i)]
                    assert len(unigram) == 1
                    featurevector.append(unigram)

            #print(featurevector,file=sys.stderr)
            extracted += 1
            tmpdata[tuple(featurevector)] += 1

        #process final pair:
        if prev:
            #process previous
            allfeaturevectors = []
            scorevector = self[prev]

            for featurevector, count in tmpdata.items():
                allfeaturevectors.append( (featurevector, count) )

            yield prev[0], prev[1], allfeaturevectors, scorevector


        print("Extracted features for " + str(extracted) + " sentences",file=sys.stderr)


    def normalize(self, sumover='s'):
        total = {}

        for sourcepattern, targetpattern, features in self.triples():
            #if not isinstance(value, list) and not isinstance(value, tuple):
            #    print("ERROR in normalize(): Expected iterable, got " + str(type(value)),file=sys.stderr)
            #    continue

            for i in range(0, min(len(features), len(sumover))):
                if sumover[i] == 's': #s|t
                    if not i in total:
                        total[i] = colibricore.PatternDict_float()
                    total[i][targetpattern] = total[i][targetpattern] + features[i]
                elif sumover[i] == 't': #t|s
                    if not i in total:
                        total[i] = colibricore.PatternDict_float()
                    total[i][sourcepattern] = total[i][sourcepattern] + features[i]



        for sourcepattern, targetpattern, features in self.triples():
            #if not isinstance(value, list) and not isinstance(value, tuple):
            #    print("ERROR in normalize(): Expected iterable, got " + str(type(value)),file=sys.stderr)
            #    continue
            #print("f: ", features,file=sys.stderr)
            for i in range(0,min(len(features),len(sumover))):
                if sumover[i] == 's': #s|t
                    try:
                        #print("s: ", features[i],"/",total[i][targetpattern],file=sys.stderr)
                        features[i] = features[i] / total[i][targetpattern]
                    except ZeroDivisionError: #ok, just leave unchanged
                        pass
                elif sumover[i] == 't': #t|s
                    try:
                        #print("t: ", features[i],"/",total[i][sourcepattern],file=sys.stderr)
                        features[i] = features[i] / total[i][sourcepattern]
                    except ZeroDivisionError: #ok, just leave unchanged
                        pass
                elif sumover[i] == '0':
                    features[i] = 0
                elif sumover[i] == '-':
                    pass

def featurestostring(features, configurations, crosslingual=False, sourcedecoder=None):
        if crosslingual and not sourcedecoder:
            raise Exception("Source decoder must be specified when doing crosslingual")
        s = []

        #sanity check
        n = 0
        for i, conf in enumerate(configurations):
            n += conf.leftcontext + conf.rightcontext
            if conf.focus: n += 1

        if len(features) < n:
            print("Configurations: ", repr(configurations),file=sys.stderr)
            print("Features: ", repr(features),file=sys.stderr)
            raise Exception("Expected " + str(n) + " features, got " + str(len(features)))

        featcursor = 0
        for i, conf in enumerate(configurations):
            n = conf.leftcontext + conf.rightcontext
            if conf.focus: n += 1

            for j in range(0,n):
                p = features[featcursor+j]
                if not isinstance(p, colibricore.Pattern):
                    raise Exception("Feature configuration ",(i,j), ": Expected Pattern, got ",str(type(p)))
                if crosslingual and conf.focus and j == conf.leftcontext:
                    feature_s = p.tostring(sourcedecoder) #override with sourcedecoder
                else:
                    feature_s = p.tostring(conf.classdecoder)
                if not feature_s:
                    print("Feature: " + str(repr(bytes(p))) ,file=sys.stderr)
                    print("Feature vector thus far: " + str(repr(s)),file=sys.stderr)
                    raise Exception("Empty feature! Not allowed!")
                s.append(feature_s)

            featcursor +=n


        return "\t".join(s)

#################################################################################################################################################3
#################################################################################################################################################3
#################################################################################################################################################3
#################################################################################################################################################3


def mosesphrasetable2alignmodel(inputfilename,sourceclassfile, targetclassfile, outfileprefix, constrainsourcemodel=None, constraintargetmodel=None,pst=0.0, pts = 0.0, joinedthreshold=0.0, divergencefrombestthreshold=0.0,nonorm=False, quiet=False):
    if not quiet: print("Reading source encoder " + sourceclassfile,file=sys.stderr)
    sourceencoder = colibricore.ClassEncoder(sourceclassfile)
    if not quiet: print("Reading target encoder " + targetclassfile,file=sys.stderr)
    targetencoder = colibricore.ClassEncoder(targetclassfile)
    if not quiet: print("Initialising featured alignment model",file=sys.stderr)
    model = AlignmentModel()
    if not quiet: print("Loading moses phrasetable",file=sys.stderr)
    scorefilter = lambda scores: scores[2] >= pts and scores[0] >= pst and scores[2] * scores[0] >= joinedthreshold
    if not quiet: print("Thresholds: pts=",pts, " pst=",pst, " joined=", joinedthreshold, " divergencefrombest=", divergencefrombestthreshold,file=sys.stderr)
    model.loadmosesphrasetable(inputfilename, sourceencoder, targetencoder, constrainsourcemodel, constraintargetmodel, False,False, "|||", 3, 0, scorefilter, divergencefrombestthreshold)
    if not quiet: print("Loaded " + str(len(model)) + " source patterns")
    if not nonorm and (constrainsourcemodel or constraintargetmodel or pst or pts):
        if not quiet: print("Normalising",file=sys.stderr)
        model.normalize('s-t-')
    if not quiet: print("Saving alignment model",file=sys.stderr)
    model.save(outfileprefix)


def main_mosesphrasetable2alignmodel():
    parser = argparse.ArgumentParser(description="Convert Moses phrasetable to Colibri alignment model", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i','--inputfile',type=str,help="Input phrasetable", action='store',required=True)
    parser.add_argument('-o','--outputfile',type=str,help="Output alignment model (file prefix without .colibri.alignmodel-* extension)", action='store',required=True)
    parser.add_argument('-S','--sourceclassfile',type=str,help="Source class file", action='store',required=True)
    parser.add_argument('-T','--targetclassfile',type=str,help="Target class file", action='store',required=True)
    parser.add_argument('-m','--constrainsourcemodel',type=str,help="Source patternmodel, used to constrain possible patterns", action='store',required=False)
    parser.add_argument('-M','--constraintargetmodel',type=str,help="Target patternmodel, used to constrain possible patterns", action='store',required=False)
    parser.add_argument('-t','--occurrencethreshold',type=int,help="Only consider patterns from constraints model that occur at least this many times",default=1, action='store',required=False)
    parser.add_argument('-l','--maxlength',type=int,help="Only consider patterns from constraints model that occur at least this many times",default=99, action='store',required=False)
    parser.add_argument('-p','--pts',type=float,help="Constrain by minimum probability p(t|s)",default=0.0, action='store',required=False)
    parser.add_argument('-P','--pst',type=float,help="Constrain by minimum probability p(s|t)", default=0.0,action='store',required=False)
    parser.add_argument('-j','--joinedconditionalprobability',type=float,help="Constrain by product of conditional probabilities: p(s|t) * p(t|s)", default=0.0,action='store',required=False)
    parser.add_argument('-d','--divergencefrombestthreshold',type=float,help="Prune translation options lower than set threshold times the strongest translation option (prunes weaker alternatives)", default=0.0,action='store',required=False)
    parser.add_argument('-N','--nonorm',help="Disable normalisation", default=False,action='store_true',required=False)
    args = parser.parse_args()

    options = colibricore.PatternModelOptions(mintokens=args.occurrencethreshold, maxlength = args.maxlength)

    if args.constrainsourcemodel:
        print("Loading source model for constraints",file=sys.stderr)
        constrainsourcemodel = colibricore.PatternSetModel(args.constrainsourcemodel, options)
        print("Patterns in constraint model: ", len(constrainsourcemodel), file=sys.stderr)
    else:
        constrainsourcemodel = None

    if args.constraintargetmodel:
        print("Loading target model for constraints",file=sys.stderr)
        constraintargetmodel = colibricore.PatternSetModel(args.constraintargetmodel, options)
    else:
        constraintargetmodel = None

    mosesphrasetable2alignmodel(args.inputfile, args.sourceclassfile, args.targetclassfile, args.outputfile, constrainsourcemodel, constraintargetmodel, args.pst, args.pts,args.nonorm, args.joinedconditionalprobability, args.divergencefrombestthreshold)

def main_extractfeatures():
    parser = argparse.ArgumentParser(description="Extract context features and build classifier data (-C) or add to alignment model", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i','--inputfile',type=str,help="Input alignment model", action='store',required=True)
    parser.add_argument('-o','--outputdir',type=str,help="Output directory, when used with -C", action='store',required=True)
    parser.add_argument('-s','--sourcemodel',type=str,help="Source model (indexed pattern model)", action='store',required=True)
    parser.add_argument('-t','--targetmodel',type=str,help="Target model (indexed pattern model)", action='store',required=True)
    parser.add_argument('-S','--sourceclassfile',type=str,help="Source class file", action='store',required=True)
    parser.add_argument('-T','--targetclassfile',type=str,help="Target class file", action='store',required=True)
    parser.add_argument('-f','--corpusfile',type=str,help="Corpus input file for feature extraction, may be specified multiple times, but all data files must cover the exact same data, i.e. have exactly the same indices (describing different factors)", action='append',required=True)
    parser.add_argument('-c','--classfile',type=str,help="Class file for the specified data file (may be specified multiple times, once per -f)", action='append',required=True)
    parser.add_argument('-l','--leftsize',type=int,help="Left context size (may be specified multiple times, once per -f)", action='append',required=True)
    parser.add_argument('-r','--rightsize',type=int,help="Right context size (may be specified multiple times, once per -f)", action='append',required=True)
    parser.add_argument('-C','--buildclassifiers',help="Build classifier training data, one classifier expert per pattern, specify a working directory in -o", action='store_true',default=False)
    parser.add_argument('-w','--weighbyoccurrence',help="When building classifier data (-C), use exemplar weighting to reflect occurrence count, rather than duplicating instances", action='store_true',default=False)
    parser.add_argument('-W','--weighbyscore',help="When building classifier data (-C), use exemplar weighting to weigh in p(t|s) from score vector", action='store_true',default=False)
    parser.add_argument('-I','--instancethreshold',type=int,help="Classifiers (-C) having less than the specified number of instances will be not be generated", action='store',default=2)
    parser.add_argument('-X','--experts', help="Classifier experts, one per source pattern", action="store_true", default=False)
    parser.add_argument('-M','--monolithic', help="Monolithic classifier", action="store_true", default=False)
    parser.add_argument('--crosslingual', help="Extract target-language context features instead of source-language features (for use with Colibrita). In this case, the corpus in -f and in any additional factor must be the *target* corpus", action="store_true", default=False)
    args = parser.parse_args()

    if not (len(args.corpusfile) == len(args.classfile) == len(args.leftsize) == len(args.rightsize)):
        print("Number of mentions of -f, -c, -l and -r has to match",file=sys.stderr)
        sys.exit(2)


    options = colibricore.PatternModelOptions(mintokens=1,doreverseindex=False)

    print("Loading alignment model",file=sys.stderr)
    model = AlignmentModel()
    model.load(args.inputfile,options)


    print("Loading source decoder " + args.sourceclassfile,file=sys.stderr)
    sourcedecoder = colibricore.ClassDecoder(args.sourceclassfile)
    print("Loading target decoder " + args.targetclassfile,file=sys.stderr)
    targetdecoder = colibricore.ClassDecoder(args.targetclassfile)

    print("Loading source model " , args.sourcemodel, file=sys.stderr)
    sourcemodel = colibricore.IndexedPatternModel(args.sourcemodel, options)

    print("Loading target model ", args.targetmodel, file=sys.stderr)
    targetmodel = colibricore.IndexedPatternModel(args.targetmodel, options)

    model.conf = []
    for corpusfile, classfile,left, right in zip(args.corpusfile, args.classfile, args.leftsize, args.rightsize):
        print("Loading corpus file ", corpusfile, file=sys.stderr)
        if classfile == args.sourceclassfile:
            d = sourcedecoder
        elif classfile == args.targetclassfile:
            d = targetdecoder
        else:
            d = colibricore.ClassDecoder(classfile)
        model.conf.append( Configuration(colibricore.IndexedCorpus(corpusfile), d ,left,True, right) )


    if args.buildclassifiers:
        if not args.monolithic and not args.experts:
            args.experts = True

        if not os.path.isdir(args.outputdir):
            try:
                os.mkdir(args.outputdir)
            except:
                print("Unable to build directory " + args.outputdir,file=sys.stderr)
                sys.exit(2)


        f = None
        prevsourcepattern = None
        firsttargetpattern = None
        prevtargetpattern = None
        trainfile = ""
        if args.monolithic:
            f = open(args.outputdir + "/train.train",'w',encoding='utf-8')
            f2 = open(args.outputdir + "/sourcepatterns.list",'w',encoding='utf-8')

        fconf = open(args.outputdir + "/classifier.conf",'wb')

        confser = []
        for conf in model.conf:
            confser.append({'corpus': conf.corpus.filename(), 'classdecoder': conf.classdecoder.filename(), 'leftcontext': conf.leftcontext, 'focus': conf.focus,'rightcontext': conf.rightcontext})
        classifierconf = { 'weighbyoccurrence': args.weighbyoccurrence, 'weighbyscore': args.weighbyscore, 'experts': args.experts, 'monolithic': args.monolithic, 'featureconf': confser}
        pickle.dump(classifierconf, fconf)
        fconf.close()


        for sourcepattern, targetpattern, featurevectors, scorevector in model.extractcontextfeatures(sourcemodel, targetmodel, model.conf, args.crosslingual):
            if prevsourcepattern is None or sourcepattern != prevsourcepattern:
                #write previous buffer to file:
                if prevsourcepattern and firsttargetpattern and prevtargetpattern and firsttargetpattern != prevtargetpattern:
                    #only bother if there are at least two distinct target options
                    if len(buffer) < args.instancethreshold:
                        print("Omitting " + trainfile + ", only " + str(len(buffer)) + " instances",file=sys.stderr)
                    else:
                        sourcepattern_s = prevsourcepattern.tostring(sourcedecoder)
                        trainfile = args.outputdir + "/" + quote_plus(sourcepattern_s) + ".train"
                        print("Writing " + trainfile,file=sys.stderr)
                        if args.experts:
                            f = open(trainfile,'w',encoding='utf-8')
                        elif args.monolithic:
                            f2.write(sourcepattern_s+"\n")
                        for line, occurrences,pts in buffer:
                            if args.weighbyscore:
                                f.write(line + "\t" + str(occurrences*pts) +  "\n")
                            elif args.weighbyoccurrence:
                                f.write(line + "\t" + str(occurrences) +  "\n")
                            else:
                                for i in range(0,occurrences):
                                    f.write(line + "\n")
                        if args.experts:
                            f.close()

                buffer = []
                prevsourcepattern = sourcepattern
                firsttargetpattern = targetpattern

            for featurevector, count in featurevectors:
                buffer.append( (featurestostring(featurevector, model.conf, args.crosslingual, sourcedecoder) + "\t" + targetpattern.tostring(targetdecoder) , count, scorevector[2] ) ) #buffer holds (ine, occurrences, pts)
                #(model.itemtostring(sourcepattern, targetpattern, featurevector,sourcedecoder, targetdecoder,False,True,False), count,scorevector[2] )  )  #buffer holds (line, occurrences, pts)

            prevtargetpattern = targetpattern


        #write last one to file:
        if prevsourcepattern and firsttargetpattern and prevtargetpattern and firsttargetpattern != prevtargetpattern:
            #only bother if there are at least two distinct target options
            if len(buffer) < args.instancethreshold:
                print("Omitting " + trainfile + ", only " + str(len(buffer)) + " instances",file=sys.stderr)
            else:
                sourcepattern_s = prevsourcepattern.tostring(sourcedecoder)
                trainfile = args.outputdir + "/" + quote_plus(sourcepattern_s) + ".train"
                print("Writing " + trainfile,file=sys.stderr)
                if args.experts:
                    f = open(trainfile,'w',encoding='utf-8')
                for line, occurrences,pts in buffer:
                    if args.weighbyscore:
                        f.write(line + "\t" + str(occurrences*pts) +  "\n")
                    elif args.weighbyoccurrence:
                        f.write(line + "\t" + str(occurrences) +  "\n")
                    else:
                        for i in range(0,occurrences):
                            f.write(line + "\n")
                if args.experts:
                    f.close()

        if args.monolithic:
            f.close()
            f2.close()




def main_alignmodel():
    parser = argparse.ArgumentParser(description="Load and view the specified alignment model", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i','--inputfile',type=str,help="Input alignment model (file prefix without .colibri.alignmodel-* extension)", action='store',required=True)
    parser.add_argument('-S','--sourceclassfile',type=str,help="Source class file", action='store',required=True)
    parser.add_argument('-T','--targetclassfile',type=str,help="Target class file", action='store',required=True)
    parser.add_argument('-p','--pts',type=float,help="Constrain by minimum probability p(t|s), assumes a moses-style score vector",default=0.0, action='store',required=False)
    parser.add_argument('-P','--pst',type=float,help="Constrain by minimum probability p(s|t), assumes a moses-style score vector", default=0.0,action='store',required=False)
    args = parser.parse_args()
    #args.storeconst, args.dataset, args.num, args.bar


    print("Loading source decoder " + args.sourceclassfile,file=sys.stderr)
    sourcedecoder = colibricore.ClassDecoder(args.sourceclassfile)
    print("Loading target decoder " + args.targetclassfile,file=sys.stderr)
    targetdecoder = colibricore.ClassDecoder(args.targetclassfile)
    print("Loading alignment model",file=sys.stderr)
    model = AlignmentModel()
    model.load(args.inputfile)
    print("Outputting",file=sys.stderr)
    if args.pts or args.pst:
        scorefilter = lambda scores: scores[2] > args.pts and scores[0] > args.pst
    else:
        scorefilter = None
    model.output(sourcedecoder,targetdecoder,scorefilter)




