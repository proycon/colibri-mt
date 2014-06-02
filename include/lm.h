#ifndef LM_H
#define LM_H

#include <pattern.h>
#include <patternstore.h>
#include <classencoder.h>
#include <classdecoder.h>
#include <map>
#include <cmath>

class LanguageModel {
    private:
        bool DEBUG;
        int order;
        ClassDecoder * classdecoder;
    public:
        PatternMap<double> ngrams;
        PatternMap<double> backoff;  
        std::map<int,unsigned int> total;
        
        LanguageModel(const std::string & filename,  ClassEncoder & encoder, ClassDecoder * classdecoder, bool debug = false);
        
        double score(const Pattern * ngram, const Pattern * history = NULL); //returns logprob (base e)        
        double scoreword(const Pattern * word, const Pattern * history = NULL); //returns logprob (base e)
                 
        int getorder() { return order; }
        size_t size() { return ngrams.size(); }
};

#endif
