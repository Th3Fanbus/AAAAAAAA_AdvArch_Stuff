/* Accumulative histogram with TBB */

#include <algorithm>
#include <cmath>
#include <iostream>
#include <iomanip>
#include <iostream>
#include <utility>
#include <vector>

#include <tbb/tbb.h>

/**
 * Print the length and contents of a vector. Assumes elements can be
 * printed using the \c << operator of \c cout directly. Attempts to
 * pad values using \c setw() so that they remain aligned.
 *
 * @param vec   The vector to print the info of
 * @param name  The name to show for this vector
 */
template<typename T>
void print_vec(const std::vector<T>& vec, const std::string& name)
{
	const std::string prefix = name + " [" + std::to_string(vec.size()) + "]:";
	std::cout << std::setw(16) << prefix;
	for (const T& e : vec) {
		std::cout << std::setw(4) << e << ",";
	}
	std::cout << std::endl;
}

/**
 * Perform a parallel reduction.
 *
 * @param input         The input vector
 * @param identity      The identity element
 * @param func          A binary operator to perform the reduction with
 *
 * @return The result of reducing the input.
 */
template<typename T, typename FuncT>
static T do_reduce(
	const std::vector<T>& input,
	const std::type_identity_t<T>& identity,
	FuncT&& func
)
{
	return oneapi::tbb::parallel_reduce(
		tbb::blocked_range<size_t>(0, input.size()),
		identity,
		[&](tbb::blocked_range<size_t> r, T result) {
			for (size_t i = r.begin(); i < r.end(); i++) {
				result = std::invoke(func, result, input[i]);
			}
			return result;
		},
		func
	);
}

/**
 * Do a parallel collection (mutable reduction). The output type can
 * differ from the input type. A collection accumulates results in a
 * container type. It can be used to calculate a minmax, or to group
 * elements in bins of some sort.
 *
 * @param input         The input vector
 * @param identity      The identity element
 * @param accumulator   Function that folds an element into a result container
 * @param combiner      Function that merges two partial result containers
 *
 * @return The result of reducing the input
 */
template<typename OutT, typename InT, typename AccT, typename CombT>
static OutT do_collect(
	const std::vector<InT>& input,
	const OutT& identity,
	AccT&& accumulator,
	CombT&& combiner
)
{
	return oneapi::tbb::parallel_reduce(
		tbb::blocked_range<size_t>(0, input.size()),
		identity,
		[&](tbb::blocked_range<size_t> r, OutT result) {
			for (size_t i = r.begin(); i < r.end(); i++) {
				std::invoke(accumulator, result, input[i]);
			}
			return result;
		},
		combiner
	);
}

/**
 * Perform a parallel map.
 *
 * @param input Input vector
 * @param func  Map function
 *
 * @return The result of mapping the input
 */
template<typename OutT, typename InT, typename FuncT>
std::vector<OutT> do_map(const std::vector<InT>& input, FuncT&& func)
{
	std::vector<OutT> output(input.size());
	oneapi::tbb::parallel_for(
		oneapi::tbb::blocked_range<size_t>(0, input.size()),
		[&](oneapi::tbb::blocked_range<size_t> r) {
			for (size_t i = r.begin(); i != r.end(); i++) {
				output[i] = std::invoke(func, input[i]);
			}
		}
	);
	return output;
}

/**
 * Calculate a parallel prefix/scan.
 *
 * The TBB function for a parallel scan takes two functions: one to
 * perform a sequential scan over a range, and another to combine two
 * summaries. This abstraction defines the former function from the
 * latter, so the caller only needs to provide the combiner function.
 *
 * @param input         Input vector
 * @param identity      The identity element
 * @param func          Binary operator to perform the scan with
 *
 * @return The result of the scan operation
 */
template<typename T, typename FuncT>
std::vector<T> do_scan(
	const std::vector<T>& input,
	const std::type_identity_t<T>& ident,
	FuncT&& func
)
{
	std::vector<T> output(input.size());
	oneapi::tbb::parallel_scan(
		oneapi::tbb::blocked_range<size_t>(0, input.size()),
		ident,
		[&](oneapi::tbb::blocked_range<size_t> r, const T& sum, const bool is_final_scan) {
			T acc = sum;
			for (size_t i = r.begin(); i != r.end(); i++) {
				acc = std::invoke(func, acc, input[i]);
				if (is_final_scan) {
					output[i] = acc;
				}
			}
			return acc;
		},
		func
	);
	return output;
}

/**
 * A mutable container to find the minimum and maximum values in a
 * series of numbers. Overloads some operators for convenience.
 */
template<typename T>
struct MinMax
{
	MinMax() = default;

	explicit MinMax(T val) : min(val), max(val) {}

	MinMax<T>& operator+=(const MinMax<T>& other)
	{
		min = std::min(min, other.min);
		max = std::max(max, other.max);
		return *this;
	}

	MinMax<T> operator+(const MinMax<T>& other) const
	{
		return MinMax<T>(*this) += other;
	}

	MinMax<T>& operator+=(const T& value)
	{
		min = std::min(min, value);
		max = std::max(max, value);
		return *this;
	}

	MinMax<T> operator+(const T& other) const
	{
		return MinMax<T>(*this) += other;
	}

	T range() const
	{
		return max - min + 1;
	}

	static const MinMax<T> identity;

	T min{std::numeric_limits<T>::max()};
	T max{std::numeric_limits<T>::min()};
};

/** Initialise the static variable in the class */
template<typename T>
const MinMax<T> MinMax<T>::identity{};

/**
 * Define the \c << operator for a \c ostream and a \c MinMax so that
 * it can easily be printed. Think of \c toString() in Java.
 */
template<typename T>
std::ostream& operator<<(std::ostream &os, const MinMax<T>& minmax)
{
	return (os << "MinMax{min=" << minmax.min << ", max=" << minmax.max << "}");
}

/**
 * Sum two vectors. If their lengths are unequal, we discard the extra
 * elements from the longer vector.
 */
template<typename T>
static std::vector<T> sum_vectors(const std::vector<T>& left, const std::vector<T>& right)
{
	/** Swap arguments so that \c left is the shortest vector */
	if (left.size() > right.size()) {
		return sum_vectors(right, left);
	}

	/** NOTE: We do this sequentially because this already runs in a parallel context */
	std::vector<T> result(left.size());
	std::transform(left.begin(), left.end(), right.begin(), result.begin(), std::plus<T>());
	return result;
}

/**
 * Representation of a histogram, plus printing.
 */
template<typename T>
class Histogram
{
protected:
	/** Draw a segment of a column of the histogram */
	void draw_hist_segment(
		std::ostream& os,
		const size_t val,
		const size_t ref,
		const bool draw_top,
		const bool draw_yval
	)
	{
		const bool draw_bot = (ref == 0) and (draw_top == draw_yval);
		if ((draw_top and val == ref) or draw_bot) {
			os << (draw_yval ? "- ######### " : "  ######### ");
		} else if (val >= ref) {
			os << (draw_yval ? "- #       # " : "  #       # ");
		} else {
			os << (draw_yval ? "- - - - - - " : "            ");
		}
	}

	/** Draw a line of the histogram plot */
	void draw_hist_line(
		std::ostream& os,
		const size_t y_val,
		const bool draw_top,
		const bool draw_yval
	)
	{
		if (draw_yval) {
			os << std::setw(9) << y_val << " - ";
		} else {
			os << std::setw(12) << "";
		}

		for (size_t x = 0; x < num_bins; x++) {
			draw_hist_segment(os, data_points[x], y_val, draw_top, draw_yval);
		}
		os << std::endl;
	}

	/** Draw the x-values for the histogram columns */
	void draw_x_values(std::ostream& os, const bool draw_to_values)
	{
		const T binsize = minmax.range() / num_bins;

		os << std::setw(9) << (draw_to_values ? "To" : "From") << "   ";
		for (size_t x = 0; x < num_bins; x++) {
			const T x_val = minmax.min + (x + draw_to_values) * binsize;
			os << std::setw(10) << x_val << "  ";
		}
		os << std::endl;
	}

public:
	/**
	 * Print the histogram.
	 *
	 * @param os            The output stream to print the histogram to
	 * @param compact_y     Use 1 row per y-value instead of 3
	 */
	void print(std::ostream& os, const bool compact_y)
	{
		const size_t hist_height = do_reduce(
			data_points,
			static_cast<size_t>(0),
			[](size_t a, size_t b) { return std::max(a, b); }
		);

		os << std::endl;
		for (size_t y = 0; y <= hist_height; y++) {
			const size_t y_val = hist_height - y;
			if (compact_y) {
				draw_hist_line(os, y_val, true, true);
			} else {
				draw_hist_line(os, y_val, true, false);
				draw_hist_line(os, y_val, false, true);
				draw_hist_line(os, y_val, false, false);
			}
		}
		draw_x_values(os, false);
		draw_x_values(os, true);
		os << std::endl;
	}

	MinMax<T> minmax{};
	size_t num_bins{};
	std::vector<size_t> data_points{};
};

/**
 * Create a histogram from the given input. May do weird stuff if the
 * data is of an integer type, because the bin range calculations are
 * done using the same input type.
 *
 * @param out_hist      The resulting histogram
 * @param input         The data to process into a histogram
 * @param num_bins      The number of bins of the histogram
 * @param cummulative   Whether to compute a cummulative histogram
 *
 * @return Zero if successful, non-zero if there was an error
 */
template<typename T>
int make_histogram(
	Histogram<T>& out_hist,
	const std::vector<T>& input,
	const size_t num_bins,
	const bool cummulative
)
{
	if (input.size() == 0 or num_bins == 0) {
		std::cerr << "E: Invalid input or number of bins specified" << std::endl;
		return -1;
	}
	print_vec(input, "input vec");

	const MinMax<T> minmax = do_collect(
		input,
		MinMax<T>::identity,
		[](MinMax<T>& acc, const T& value) { acc += value; },
		std::plus<MinMax<T>>()
	);
	if (minmax.min > minmax.max) {
		std::cerr << "E: Could not find bounds of input (bug?)" << std::endl;
		return -1;
	}

	std::cout << minmax << std::endl;

	const T data_start = minmax.min;
	const T binsize = minmax.range() / num_bins;

	if (binsize * num_bins != minmax.range()) {
		std::cerr << "W: Possible precision loss (using integer types?)" << std::endl;
	}

	std::vector<size_t> bin_indices = do_map<size_t>(input, [&](const T& value) {
		return std::floor((value - data_start) / binsize);
	});
	print_vec(bin_indices, "bin idx");

	const std::vector<size_t> bin_amounts = do_collect(
		bin_indices,
		std::vector<size_t>(num_bins),
		[](std::vector<size_t>& acc, const size_t value) { acc[value]++; },
		sum_vectors<size_t>
	);

	print_vec(bin_amounts, "bin amount");

	if (not cummulative) {
		out_hist = { minmax, num_bins, bin_amounts };
		return 0;
	}

	std::vector<size_t> bin_accam = do_scan(
		bin_amounts,
		static_cast<size_t>(0),
		std::plus<size_t>()
	);

	print_vec(bin_accam, "bin accam");

	out_hist = { minmax, num_bins, bin_accam };

	return 0;
}

/** For demonstration purposes, makes and prints a histogram */
template<typename T>
static int draw_histogram(
	std::ostream& os,
	const std::vector<T>& input,
	const size_t num_bins,
	const bool cummulative,
	const bool draw_compact_y
)
{
	Histogram<T> hist;
	if (const int rc = make_histogram(hist, input, num_bins, cummulative)) {
		return rc;
	}
	hist.print(os, draw_compact_y);
	return 0;
}

int main()
{
	const std::vector<double> input{7, 1, 0, 13, 0, 15, 20, -1};

	draw_histogram(std::cout, input, 6, false, false);	/* Non-cummulative histogram */
	draw_histogram(std::cout, input, 4, true, true);	/* Cummulative histogram */

	return 0;
}
