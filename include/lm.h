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
        PatternMap<double> backoff; //MAYBE TODO: merge with ngrams? <EncNGram, pair<double,double> > ?
        std::map<int,unsigned int> total;
        
        LanguageModel(const std::string & filename,  ClassEncoder & encoder, ClassDecoder * classdecoder, bool debug = false);
        
        double score(const Pattern * ngram, const Pattern * history = NULL); //returns logprob (base e)        
        double scoreword(const Pattern * word, const Pattern * history = NULL); //returns logprob (base e)
                 
        //double score(EncNGram ngram); //returns logprob (base 10)
        //double score(EncData & data, bool fullsentence = false); //returns logprob (base 10)
        
        int getorder() { return order; }
        size_t size() { return ngrams.size(); }
};

#endif
