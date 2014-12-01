#!/usr/bin/env python3

import sys
import os
import unittest
import colibricore
import glob
from colibrimt.alignmentmodel import AlignmentModel

class TestExperiment(unittest.TestCase):
    def test001_alignmodel(self):
        """Checking alignment model"""
        options = colibricore.PatternModelOptions(mintokens=1,doreverseindex=False)

        s = colibricore.ClassEncoder("test-en-nl/test-en-train.colibri.cls")
        t = colibricore.ClassEncoder("test-en-nl/test-nl-train.colibri.cls")
        sdec = colibricore.ClassDecoder("test-en-nl/test-en-train.colibri.cls")
        tdec = colibricore.ClassDecoder("test-en-nl/test-nl-train.colibri.cls")

        print("Loading alignment model",file=sys.stderr)
        model = AlignmentModel()
        model.load("test-en-nl/test-en-nl.colibri.alignmodel",options)
        print("Loaded",file=sys.stderr)
        model.output(sdec,tdec)
        print("Testing contents",file=sys.stderr)
        self.assertTrue(  (s.buildpattern('a'), t.buildpattern('een') ) in model )
        self.assertTrue(  (s.buildpattern('just'), t.buildpattern('maar') ) in model )
        self.assertTrue(  (s.buildpattern('only'), t.buildpattern('maar') ) in model )
        self.assertTrue(  (s.buildpattern('bank'), t.buildpattern('oever') ) in model )
        self.assertTrue(  (s.buildpattern('bank'), t.buildpattern('bank') ) in model )
        self.assertTrue(  (s.buildpattern('bank'), t.buildpattern('sturen') ) in model )
        self.assertTrue(  (s.buildpattern('couch'), t.buildpattern('bank') ) in model )
        self.assertTrue(  (s.buildpattern('the bank'), t.buildpattern('de oever') ) in model )
        self.assertTrue(  (s.buildpattern('the bank'), t.buildpattern('de bank') ) in model )
        self.assertTrue(  (s.buildpattern('the couch'), t.buildpattern('de bank') ) in model )
        self.assertEqual(  len(list(model.triples())), 10 )


    def test002_sourcedump(self):
        """Verifying source dump"""
        r = os.system("diff test-en-nl/test-en-nl.phrasetable.sourcedump test-en-nl.phrasetable.sourcedump.ok")
        self.assertEqual(r,0)

    def test003_targetdump(self):
        """Verifying target dump"""
        r = os.system("diff test-en-nl/test-en-nl.phrasetable.targetdump test-en-nl.phrasetable.targetdump.ok")
        self.assertEqual(r,0)

    def test004_trainfiles_X(self):
        """Verifying training instances for experts"""
        self.assertEqual(  len(list(glob.glob("test-en-nl/classifierdata-XI2l1r1/*.train"))), 2)
        r = os.system("diff test-en-nl/classifierdata-XI2l1r1/bank.train bank.train.ok")
        self.assertEqual(r,0)
        r = os.system("diff test-en-nl/classifierdata-XI2l1r1/the+bank.train the+bank.train.ok")
        self.assertEqual(r,0)

    def test004_trainfiles_M(self):
        """Verifying training instances for monolithic system"""
        self.assertEqual(  len(list(glob.glob("test-en-nl/classifierdata-MI2l1r1/*.train"))), 1)
        r = os.system("diff test-en-nl/classifierdata-MI2l1r1/train.train train.train.ok")
        self.assertEqual(r,0)

if __name__ == '__main__':
        if not os.path.exists("test.py"):
            print("Please run the test from the test/ directory",file=sys.stderr)
            sys.exit(2)

        print("Cleanup",file=sys.stderr)
        if os.path.exists("test-en-nl"):
            os.system("rm -Rf test-en-nl")
        os.system("mkdir test-en-nl")
        os.system("cp test-en-nl.phrasetable test-en-nl/")

        print("Running test experiment",file=sys.stderr)
        r = os.system("./exp-test.sh")

        unittest.main()

