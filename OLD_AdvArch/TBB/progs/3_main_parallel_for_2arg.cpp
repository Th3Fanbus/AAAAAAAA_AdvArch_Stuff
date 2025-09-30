#include <oneapi/tbb/info.h>
#include <oneapi/tbb/parallel_for.h>
#include <cassert>
#include <iostream>
#include <cmath>
#include <vector>

#include <random>
#include <time.h>
#include <thread>

#if defined (_MSC_VER)  // Visual studio
    #define thread_local __declspec( thread )
#elif defined (__GCC__) // GCC
    #define thread_local __thread
#endif

/*
 * Thread-safe function that returns a random number between min and max (inclusive).
 * This function takes ~142% the time that calling rand() would take. For this extra
 * cost you get a better uniform distribution and thread-safety.
 */
int int_rand(const int& min, const int& max) {
    static thread_local std::mt19937* generator = nullptr;
    if (!generator) {
        generator = new std::mt19937(std::clock() + std::hash<std::thread::id>()(std::this_thread::get_id()));
    }
    std::uniform_int_distribution<int> distribution(min, max);
    return distribution(*generator);
}

template<typename T, typename G>
static void initialise_array(std::vector<T>& vec, const G generator)
{
    oneapi::tbb::parallel_for(
        oneapi::tbb::blocked_range<int>(0, vec.size()),
        [&](tbb::blocked_range<int> r) {
            for (int i = r.begin(); i < r.end(); i++){
                vec[i] = generator();
            }
        }
    );
}

template<typename T, typename F>
static void binary_transform(const std::vector<T> va, const std::vector<T> vb, std::vector<T>& out, F function)
{
    oneapi::tbb::parallel_for(
        oneapi::tbb::blocked_range<int>(0, std::min(va.size(), vb.size())),
        [&](tbb::blocked_range<int> r){
            for (int i = r.begin(); i < r.end(); i++){
                out[i] = function(va[i], vb[i]);
            }
        }
    );
}

#define VECTOR_SIZE 10000000

int main()
{
    // Get the default number of threads
    int num_threads = oneapi::tbb::info::default_concurrency();
    std::cout << "Default concurrency " << num_threads << std::endl;

    std::vector<int> vec_x = std::vector<int>(VECTOR_SIZE);
    std::vector<int> vec_y = std::vector<int>(VECTOR_SIZE);
    std::vector<int> vec_z = std::vector<int>(VECTOR_SIZE);

    auto generator = []() { return int_rand(0, 100); };
    initialise_array(vec_x, generator);
    initialise_array(vec_y, generator);

    binary_transform(vec_x, vec_y, vec_z, [](int a, int b) { return a + b; });

    for (int i = 0; i < VECTOR_SIZE; i++) {
        assert(vec_z[i] == vec_x[i] + vec_y[i]);
    }

    double total = 0;
    for (double value : vec_z) {
        total += value;
    }

    std::cout << "Total " << total << std::endl;
    return 0;
}
