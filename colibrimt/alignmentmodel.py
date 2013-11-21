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


class AlignmentModel:
    def __init__(self, multivalue=True, singleintvalue=False):
        self.values = {}
        self.newvalueid = 0
        self.alignedpatterns = colibricore.AlignedPatternDict_int32()
        self.multivalue = multivalue
        self.singleintvalue = singleintvalue

    def add(self, sourcepattern, targetpattern, value):
        if not isinstance(sourcepattern, colibricore.Pattern):
            raise ValueError("Source pattern must be instance of Pattern")
        if not isinstance(targetpattern, colibricore.Pattern):
            raise ValueError("Target pattern must be instance of Pattern")

        if (sourcepattern, targetpattern) in self.alignedpatterns:
            valueid = self.alignedpatterns[(sourcepattern, targetpattern)]
            if self.singleintvalue:
                self.alignedpatterns[(sourcepattern,targetpattern)] = value
            elif self.multivalue:
                self.values[valueid].append(value)
            else:
                self.values[valueid] = value
        else:
            self.newvalueid += 1
            valueid = self.newvalueid
            if self.singleintvalue:
                self.alignedpatterns[(sourcepattern,targetpattern)] = value
            elif self.multivalue:
                self.alignedpatterns[(sourcepattern,targetpattern)] = valueid
                self.values[valueid] = [value]
            else:
                self.alignedpatterns[(sourcepattern,targetpattern)] = valueid
                self.values[valueid] = value

    def __len__(self):
        return len(self.alignedpatterns)

    def __iter__(self):
        if self.singleintvalue:
            for sourcepattern, targetpattern, value in self.alignedpatterns.items():
                yield sourcepattern, targetpattern, value
        else:
            for sourcepattern, targetpattern, valueid in self.alignedpatterns.items():
                yield sourcepattern, targetpattern, self.values[valueid]

    def sourcepatterns(self):
        for sourcepattern in self.alignedpatterns:
            yield sourcepattern


    def targetpatterns(self, sourcepattern=None):
        if sourcepattern is None:
            s = colibricore.PatternSet() #//segfaults (after 130000+ entries)? can't figure out why yet
            #s = set()
            for sp in self.alignedpatterns:
                for targetpattern in self.alignedpatterns.children(sp):
                    s.add(targetpattern)

            for targetpattern in s:
                yield targetpattern
        else:
            for targetpattern in self.alignedpatterns.children(sourcepattern):
                yield targetpattern

    def items(self):
        return iter(self)

    def itemcount(self):
        count = 0
        for _ in self:
            count += 1
        return count

    def __getitem__(self, item):
        if self.singleintvalue:
            return self.alignedpatterns[item]
        else:
            return self.values[self.alignedpatterns[item]]

    def __setitem__(self, item, value):
        if self.singleintvalue:
            self.alignedpatterns[item] = value
        else:
            if not item in self.alignedpatterns:
                self.newvalueid +=1
                self.alignedpatterns[item] = self.newvalueid
            self.values[self.alignedpatterns[item]] = value


    def __contains__(self, item):
        return item in self.alignedpatterns

    def haspair(self, sourcepattern, targetpattern):
        return self.alignedpatterns.haspair(sourcepattern, targetpattern)

    def load(self, fileprefix):
        self.alignedpatterns.read(fileprefix + ".colibri.alignmodel-keys")
        print( "Loaded keys: alignments for " + str(len(self.alignedpatterns)) + " source patterns",file=sys.stderr)
        if os.path.exists(fileprefix + ".colibri.alignmodel-values"):
            self.singleintvalue= False
            with open(fileprefix + ".colibri.alignmodel-values",'rb') as f:
                self.values = pickle.load(f)
            #check if we are multivalued
            for key, value in self.values.items():
                self.multivalue = (isinstance(value, tuple) or isinstance(value, list))
                break
            print( "Loaded values (" + str(len(self.values)) + ")",file=sys.stderr)
        else:
            self.singleintvalue= True

    def save(self, fileprefix):
        """Output"""
        self.alignedpatterns.write(fileprefix + ".colibri.alignmodel-keys")
        if not self.singleintvalue:
            with open(fileprefix + ".colibri.alignmodel-values",'wb') as f:
                pickle.dump(self.values, f)

    def output(self, sourcedecoder, targetdecoder, scorefilter=None):
        for sourcepattern, targetpattern, value in self.items():
            if scorefilter and not scorefilter(value): continue
            print(sourcepattern.tostring(sourcedecoder) + "\t" ,end="")
            print(targetpattern.tostring(targetdecoder) + "\t" ,end="")
            if not self.multivalue or self.singleintvalue:
                print(str(value))
            else:
                for v in value:
                    print(str(v) + "\t" ,end="")
            print()



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

    def _normaux(self, sourcepattern, targetpattern, total_s, total_t, value, index, sumover):
        if sumover == 's':
            total_s[sourcepattern] += value[index]
        elif sumover == 't':
            total_t[targetpattern] += value[index]
        else:
            raise Exception("sumover can't be " + sumover)


class FeatureConfiguration:
    def __init__(self):
        self.conf = []
        self.decoders = {}

    def addfactorfeature(self, classdecoder, leftcontext=0, focus=True,rightcontext=0):
        if isinstance(classdecoder, colibricore.ClassDecoder):
            self.decoders[classdecoder.filename] = classdecoder
            classdecoder = classdecoder.filename
        elif not isinstance(classdecoder,str):
            raise ValueError
        self.conf.append( ( colibricore.Pattern, classdecoder, leftcontext, focus, rightcontext) )

    def addfeature(self, type):
        """Will not be propagated to Moses phrasetable"""
        self.conf.append( ( type,False) )

    def addscorefeature(self, type):
        """Will be propagated to Moses phrasetable"""
        self.conf.append( ( type,True) )


    def __len__(self):
        return len(self.conf)

    def __iter__(self):
        for x in self.conf:
            yield x

    def __getitem__(self, index):
        return self.conf[index]


    def loaddecoders(self, *args):
        for item in self:
            if item[0] == colibricore.Pattern:
                decoderfile = item[1]
                if decoderfile not in self.decoders:
                    foundinargs = False
                    for x in args:
                        if x.filename == decoderfile:
                            self.decoders[x.filename] = x
                    if not foundinargs:
                        self.decoders[decoderfile] = colibricore.ClassDecoder(decoderfile)


class FeaturedAlignmentModel(AlignmentModel):
    def __init__(self, conf=FeatureConfiguration()):
        assert isinstance(conf, FeatureConfiguration)
        self.conf = conf
        super().__init__(True,False)


    def load(self, fileprefix):
        if os.path.exists(fileprefix + ".colibri.alignmodel-featconf"):
            with open(fileprefix + ".colibri.alignmodel-featconf",'rb') as f:
                self.conf.conf = pickle.load(f)
        super().load(fileprefix)

    def save(self, fileprefix):
        with open(fileprefix + ".colibri.alignmodel-featconf",'wb') as f:
            pickle.dump(self.conf.conf, f)
        super().save(fileprefix)

    def __iter__(self):
        for sourcepattern, targetpattern, valueid in self.alignedpatterns.items():
            for featurevector in self.values[valueid]: #multiple feature vectors per alignment possible
                yield sourcepattern, targetpattern, featurevector

    def output(self, sourcedecoder, targetdecoder, *preloadeddecoders):
        preloadeddecoders = (sourcedecoder, targetdecoder) +  preloadeddecoders
        self.conf.loaddecoders(*preloadeddecoders)

        print("Configuration:",len(self.conf),file=sys.stderr)


        for sourcepattern, targetpattern, features in self.items():
            print(sourcepattern.tostring(sourcedecoder) + "\t" ,end="")
            print(targetpattern.tostring(targetdecoder) + "\t" ,end="")
            if len(features) < len(self.conf):
                print(repr(self.conf.conf),file=sys.stderr)
                print(repr(features),file=sys.stderr)
                raise Exception("Expected " + str(len(self.conf)) + " features, got " + str(len(features)))
            it = iter(features)
            for i, conf in enumerate(self.conf):
                if conf[0] == colibricore.Pattern:
                    _, classdecoder, leftcontext, dofocus, rightcontext = conf
                    classdecoder = self.conf.decoders[classdecoder]
                    n = leftcontext + rightcontext
                    if dofocus: n += 1
                    for j in range(0,n):
                        p = next(it)
                        print(p.tostring(classdecoder) ,end="")
                        if i < len(self.conf) -1:
                            #not the last feature yet:
                            print("\t",end="")
                else:
                    print(str(next(it)) + "\t" ,end="")
            print()

    def savemosesphrasetable(self, filename, sourcedecoder, targetdecoder):
        """Output for moses"""
        with open(filename,'w',encoding='utf-8') as f:
            for sourcepattern, targetpattern, features in self:
                f.write(sourcepattern.tostring(sourcedecoder) + " ||| " + targetpattern.tostring(targetdecoder) + " ||| ")
                for i, feature, featureconf in enumerate(zip(features, self.conf)):
                    if featureconf[0] != colibricore.Pattern and featureconf[1]:
                        if (i > 0): f.write(" ")
                        f.write(str(feature))
                f.write("\n")

    def loadmosesphrasetable(self, filename, sourceencoder, targetencoder,constrainsourcemodel=None,constraintargetmodel=None, quiet=False, reverse=False, delimiter="|||", score_column = 3, max_sourcen = 0, scorefilter = lambda x:True):
        """Load a phrase table from file into memory (memory intensive!)"""
        self.phrasetable = {}

        if filename.split(".")[-1] == "bz2":
            f = bz2.BZ2File(filename,'r')
        elif filename.split(".")[-1] == "gz":
            f = gzip.GzipFile(filename,'r')
        else:
            f = open(filename,'r',encoding='utf-8')
        linenum = 0
        prevsource = None
        targets = []


        added = 0
        skipped = 0

        haswordalignments = False

        while True:
            if not quiet:
                linenum += 1
                if (linenum % 100000) == 0:
                    print("Loading phrase-table: @" + str(linenum) + "\t(" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ") total added: " + str(added) + ", skipped: " + str(skipped),file=sys.stderr)
            line = f.readline()
            if not line:
                break

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

            if scorefilter:
                if not scorefilter(scores): continue

            if len(segments) >= 4:
                scores.append( [ tuple([int(y) for y in x.split('-')]) for x in segments[3].split() ] )
                haswordalignments = True
            elif haswordalignments:
                scores.append([])


            if reverse:
                if max_sourcen > 0 and segments[1].count(' ') + 1 > max_sourcen:
                    continue

                source = sourceencoder.buildpattern(segments[1]) #tuple(segments[1].split(" "))
                target = targetencoder.buildpattern(segments[0]) #tuple(segments[0].split(" "))
            else:
                if max_sourcen > 0 and segments[0].count(' ') + 1 > max_sourcen:
                    continue

                source = sourceencoder.buildpattern(segments[0]) #tuple(segments[0].split(" "))
                target = targetencoder.buildpattern(segments[1]) #tuple(segments[1].split(" "))

            if constrainsourcemodel and source not in constrainsourcemodel:
                skipped += 1
                continue
            if constraintargetmodel and target not in constraintargetmodel :
                skipped += 1
                continue

            added += 1
            self.add(source,target, scores)

        f.close()

        self.conf = FeatureConfiguration()
        l = len(scores)
        if haswordalignments:
            l = l - 1
        for x in range(0,l):
            self.conf.addscorefeature(float)
        if haswordalignments:
            self.conf.addfeature(list)

    def patternswithindexes(self, sourcemodel, targetmodel):
        """Finds occurrences (positions in the source and target models) for all patterns"""
        for sourcepattern in self.sourcepatterns():
            if not sourcepattern in sourcemodel:
                print("Warning: a pattern from the phrase table was not found in the source model (pruned for not meeting a threshold most likely)" ,file=sys.stderr)
                continue
            sourceindexes = sourcemodel[sourcepattern]
            for targetpattern in self.targetpatterns(sourcepattern):
                if not targetpattern in targetmodel:
                    print("Warning: a pattern from the phrase table was not found in the target model (pruned for not meeting a threshold most likely)" ,file=sys.stderr)
                    continue
                targetindexes = targetmodel[targetpattern]

                #for every occurrence of this pattern in the source
                for sentence, token in sourceindexes:
                    #is a target pattern found in the same sentence? (if so we *assume* they're aligned, we don't actually use the word alignments anymore here)
                    targetmatch = False
                    for targetsentence,targettoken in targetindexes:
                        if sentence == targetsentence:
                            yield sourcepattern, targetpattern, sentence, token, targetsentence, targettoken
                            targetmatch = True
                            break


    def extractfactorfeatures(self, sourcemodel, targetmodel, factoredcorpora):
        featurevector = []
        assert isinstance(sourcemodel, colibricore.IndexedPatternModel)
        assert isinstance(targetmodel, colibricore.IndexedPatternModel)

        factorconf = [x for x in self.conf if x[0] == colibricore.Pattern ]
        if len(factoredcorpora) != len(factorconf):
            raise ValueError("Expected " + str(len(factorconf)) + " instances in factoredcorpora, got " + str(len(factoredcorpora)))

        if not all([ isinstance(x,colibricore.IndexedCorpus) for x in factoredcorpora]):
            raise ValueError("factoredcorpora elements must be instances of IndexedCorpus")


        for sourcepattern, targetpattern, sentence, token,_,_ in self.patternswithindexes(sourcemodel, targetmodel):
            n = len(sourcepattern)
            featurevector= []
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
            yield sentence, token, sourcepattern, targetpattern, featurevector



    def normalize(self, sumover='s'):
        if self.singleintvalue:
            raise Exception("Can't normalize AlignedPatternDict with singleintvalue set")

        total = {}

        for sourcepattern, targetpattern, features in self:
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



        for sourcepattern, targetpattern, features in self:
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


def mosesphrasetable2alignmodel(inputfilename,sourceclassfile, targetclassfile, outfileprefix, constrainsourcemodel=None, constraintargetmodel=None,pst=0.0, pts = 0.0,nonorm=False, quiet=False):
    if not quiet: print("Reading source encoder " + sourceclassfile,file=sys.stderr)
    sourceencoder = colibricore.ClassEncoder(sourceclassfile)
    if not quiet: print("Reading target encoder " + targetclassfile,file=sys.stderr)
    targetencoder = colibricore.ClassEncoder(targetclassfile)
    if not quiet: print("Initialising featured alignment model",file=sys.stderr)
    model = FeaturedAlignmentModel()
    if not quiet: print("Loading moses phrasetable",file=sys.stderr)
    if pts or pst:
        scorefilter = lambda scores: scores[2] > pts and scores[0] > pst
    else:
        scorefilter = None
    model.loadmosesphrasetable(inputfilename, sourceencoder, targetencoder, constrainsourcemodel, constraintargetmodel, False,False, "|||", 3, 0, scorefilter)
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
    parser.add_argument('-p','--pts',type=float,help="Constrain by minimum probability p(t|s)",default=0.0, action='store',required=False)
    parser.add_argument('-P','--pst',type=float,help="Constrain by minimum probability p(s|t)", default=0.0,action='store',required=False)
    parser.add_argument('-N','--nonorm',help="Disable normalisation", default=False,action='store_true',required=False)
    args = parser.parse_args()

    if args.constrainsourcemodel:
        print("Loadin source model for constraints",file=sys.stderr)
        constrainsourcemodel = colibricore.UnindexedPatternModel(args.constrainsourcemodel)
    else:
        constrainsourcemodel = None

    if args.constraintargetmodel:
        print("Loading target model for constraints",file=sys.stderr)
        constraintargetmodel = colibricore.UnindexedPatternModel(args.constraintargetmodel)
    else:
        constraintargetmodel = None

    mosesphrasetable2alignmodel(args.inputfile, args.sourceclassfile, args.targetclassfile, args.outputfile, constrainsourcemodel, constraintargetmodel, args.pst, args.pts,args.nonorm)

def main_extractfeatures():
    parser = argparse.ArgumentParser(description="Extract context features and add to alignment model", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i','--inputfile',type=str,help="Input alignment model (file prefix without .colibri.alignmodel-* extension)", action='store',required=True)
    parser.add_argument('-o','--outputfile',type=str,help="Output alignment model (file prefix without .colibri.alignmodel-* extension)", action='store',required=True)
    parser.add_argument('-s','--sourcemodel',type=str,help="Source model (indexed pattern model)", action='store',required=True)
    parser.add_argument('-t','--targetmodel',type=str,help="Target model (indexed pattern model)", action='store',required=True)
    parser.add_argument('-f','--corpusfile',type=str,help="Corpus input file for feature extraction, may be specified multiple times, but all data files must cover the exact same data, i.e. have exactly the same indices (describing different factors)", action='append',required=True)
    parser.add_argument('-c','--classfile',type=str,help="Class file for the specified data file (may be specified multiple times, once per -f)", action='append',required=True)
    parser.add_argument('-l','--leftsize',type=int,help="Left context size (may be specified multiple times, once per -f)", action='append',required=True)
    parser.add_argument('-r','--rightsize',type=int,help="Right context size (may be specified multiple times, once per -f)", action='append',required=True)
    args = parser.parse_args()

    if not (len(args.corpusfile) == len(args.classfile) == len(args.leftsize) == len(args.rightsize)):
        print("Number of mentions of -f, -c, -l and -r has to match",file=sys.stderr)
        sys.exit(2)


    print("Loading alignment model",file=sys.stderr)
    model = FeaturedAlignmentModel()
    model.load(args.inputfile)


    print("Loading source model " , args.sourcemodel, file=sys.stderr)
    sourcemodel = colibricore.IndexedPatternModel(args.sourcemodel)

    print("Loading target model ", args.targetmodel, file=sys.stderr)
    targetmodel = colibricore.IndexedPatternModel(args.targetmodel)

    corpora = []
    for corpusfile in args.corpusfile:
        print("Loading corpus file ", corpusfile, file=sys.stderr)
        corpora.append(colibricore.IndexedCorpus(corpusfile))

    #classdecoders = []
    #for classfile in args.classfile:
    #    print("Loading corpus file ", classfile, file=sys.stderr)
    #    classdecoders.append(colibricore.ClassDecoder(classfile))

    #add feature configuration
    for corpus, classfile,left, right in zip(corpora,args.classfile,args.leftsize, args.rightsize):
        model.conf.addfactorfeature(classfile,left,right)

    model.extractfactorfeatures(sourcemodel, targetmodel, corpora)



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
    if os.path.exists(args.inputfile + ".colibri.alignmodel-featconf"):
        model = FeaturedAlignmentModel()
    else:
        model = AlignmentModel()
    model.load(args.inputfile)
    print("Outputting",file=sys.stderr)
    if args.pts or args.pst:
        scorefilter = lambda scores: scores[2] > args.pts and scores[0] > args.pst
    else:
        scorefilter = None
    model.output(sourcedecoder,targetdecoder,scorefilter)




