#!/usr/bin/env python3

import sys
import os
import unittest
import colibricore
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
        self.assertTrue(  (s.buildpattern('bank'), t.buildpattern('over') ) in model )
        self.assertTrue(  (s.buildpattern('bank'), t.buildpattern('bank') ) in model )
        self.assertTrue(  (s.buildpattern('bank'), t.buildpattern('sturen') ) in model )
        self.assertTrue(  (s.buildpattern('couch'), t.buildpattern('bank') ) in model )
        self.assertTrue(  (s.buildpattern('the bank'), t.buildpattern('de oever') ) in model )
        self.assertTrue(  (s.buildpattern('the bank'), t.buildpattern('de bank') ) in model )
        self.assertTrue(  (s.buildpattern('the couch'), t.buildpattern('de bank') ) in model )
        self.assertEqual(  len(model), 10 )


    def test002_sourcedump(self):
        """Verifying source dump"""
        r = os.system("diff test-en-nl/test-en-nl.phrasetable.sourcedump test-en-nl.phrasetable.sourcedump.ok")
        self.assertEqual(r,0)

    def test003_targetdump(self):
        """Verifying target dump"""
        r = os.system("diff test-en-nl/test-en-nl.phrasetable.targetdump test-en-nl.phrasetable.targetdump.ok")
        self.assertEqual(r,0)

if __name__ == '__main__':
        print("Cleanup",file=sys.stderr)
        os.system("rm -Rf test-en-nl > /dev/null 2> /dev/null")

        print("Running test experiment",file=sys.stderr)
        r = os.system("./exp-test.sh")

        unittest.main()

