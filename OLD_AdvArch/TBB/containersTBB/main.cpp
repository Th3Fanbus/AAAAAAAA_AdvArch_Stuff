//https://docs.oneapi.io/versions/latest/onetbb/tbb_userguide/concurrent_hash_map.html
#include <iostream>
#include <vector>
#include <algorithm>


#include <tbb/tbb.h>
#include "oneapi/tbb/concurrent_hash_map.h"
#include "oneapi/tbb/blocked_range.h"
#include "oneapi/tbb/parallel_for.h"
#include <string>


using namespace oneapi::tbb;
using namespace std;


const size_t N = 1000000;
string Data[N];



// Structure that defines hashing and comparison operations for user's type.
struct MyHashCompare {
    static size_t hash( const string& x ) {
        size_t h = 0;
        for( const char* s = x.c_str(); *s; ++s )
            h = (h*17)^*s;
        return h;
    }
    //! True if strings are equal
    static bool equal( const string& x, const string& y ) {
        return x==y;
    }
};


// A concurrent hash table that maps strings to ints.
typedef concurrent_hash_map<string,int,MyHashCompare> StringTable;


// Function object for counting occurrences of strings.
struct Tally {
    StringTable& table;
    Tally( StringTable& table_ ) : table(table_) {}
    void operator()(const blocked_range<string*> range) const {
        for(string* p=range.begin(); p!=range.end(); ++p ) {
            StringTable::accessor a;
            table.insert( a, *p );
            a->second += 1;
        }
    }
};



 


StringTable table;

int main(){
    static int length_word = 4;
    
    //Can we parallelize this init?
    for (int j=0;j<N;j++){
        string s="";
        for (int i=0;i<length_word;i++){
            s += "a"+(rand()%26);
        }
        Data[j]=s;
    }
    

    tbb::tick_count t0 = tbb::tick_count::now();
    parallel_for( blocked_range<string*>( Data, Data+N, 1000 ),
                  Tally(table));
    
    // for( StringTable::iterator i=table.begin(); i!=table.end(); ++i )
    //     printf("%s %d\n",i->first.c_str(),i->second);

    cout << "\nTime: " << (tbb::tick_count::now()-t0).seconds() << "seconds" << endl;    
    return 0;

 }
