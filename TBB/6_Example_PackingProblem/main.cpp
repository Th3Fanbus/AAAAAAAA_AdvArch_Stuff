#include <iostream>
#include <vector>
#include <algorithm>

#include <tbb/tbb.h>
#include "oneapi/tbb/blocked_range.h"
#include "oneapi/tbb/parallel_for.h"

using namespace std;
using namespace oneapi;

vector<int> doMAP(int a,int x[], int n)
{
    vector<int> out(n);

    tbb::parallel_for(
        tbb::blocked_range<int>(0, n),

        // lambda function
        [&](tbb::blocked_range<int> r) {
            for (auto i = r.begin(); i != r.end(); i++) {
                out[i] = x[i]>=a;
            }
        }

    );
    return out;
}


int doSCAN(int out[], const int in[],int n){
    int total_sum = tbb::parallel_scan(
        tbb::blocked_range<int>(0, n), //range
        0, //id
        [&](tbb::blocked_range<int> r, int sum, bool is_final_scan){        
            int tmp = sum;
            for (int i = r.begin(); i < r.end(); ++i) {
                tmp = tmp + in[i];
                if (is_final_scan)
                    out[i] = tmp;
            }
            return tmp;
        },
        [&]( int left, int right ) {
            return left + right;
        }
    );
    return total_sum;
}

//doMAPFilter(&out[0],&ix[0],&x[0],&filter_results[0], x.size())
void doMAPFilter(int bolMatch[], int ixMatch[],int x[], int out[], int n){
    tbb::parallel_for(
        tbb::blocked_range<int>(0, n),
        // lambda function
        [&](tbb::blocked_range<int> r) {
            for (auto i = r.begin(); i < r.end(); i++) {
                if (bolMatch[i]){
                    out[ixMatch[i]-1] = x[i];    
                }
            }
        }
    );
}

int main(){

    static int a = 10;
    static vector<int> x{7,1,0,13,0,15,20,-1};

	tbb::tick_count t0 = tbb::tick_count::now();
 	
    //MAP operation
    vector<int> bolMatch = doMAP(a,&x[0], x.size());
 	
    cout << "Map vector: "<< endl;
    for (int i: bolMatch){
        cout << i << ',';
    }
    cout << endl;

    //SCAN
    vector<int> ixMatch(x.size());
    int sum = doSCAN(&ixMatch[0], &bolMatch[0],  x.size()); //get index order

    cout << "Scan vector: " << sum << endl;
    for (int i: ixMatch){
        cout << i << ',';
    }
    cout << endl;

    //JOIN
    vector<int> filtered_results(sum);
    doMAPFilter(&bolMatch[0],&ixMatch[0],&x[0],&filtered_results[0], x.size());


    cout << "Filtered vector: " << endl;
    for (int i: filtered_results){
        cout << i << ',';
    }
    cout << endl;

 	cout << "\nTime: " << (tbb::tick_count::now()-t0).seconds() << "seconds" << endl;

 	return 0;

 }
