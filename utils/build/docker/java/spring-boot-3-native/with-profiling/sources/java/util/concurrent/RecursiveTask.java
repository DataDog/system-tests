/*
 * ORACLE PROPRIETARY/CONFIDENTIAL. Use is subject to license terms.
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 */

/*
 *
 *
 *
 *
 *
 * Written by Doug Lea with assistance from members of JCP JSR-166
 * Expert Group and released to the public domain, as explained at
 * http://creativecommons.org/publicdomain/zero/1.0/
 */

package java.util.concurrent;

/**
 * A recursive result-bearing {@link ForkJoinTask}.
 *
 * <p>For example, here is a task-based program for computing Factorials:
 *
 * <pre> {@code
 * import java.util.concurrent.RecursiveTask;
 * import java.math.BigInteger;
 * public class Factorial {
 *   static class FactorialTask extends RecursiveTask<BigInteger> {
 *     private final int from, to;
 *     FactorialTask(int from, int to) { this.from = from; this.to = to; }
 *     protected BigInteger compute() {
 *       int range = to - from;
 *       if (range == 0) {                       // base case
 *         return BigInteger.valueOf(from);
 *       } else if (range == 1) {                // too small to parallelize
 *         return BigInteger.valueOf(from).multiply(BigInteger.valueOf(to));
 *       } else {                                // split in half
 *         int mid = from + range / 2;
 *         FactorialTask leftTask = new FactorialTask(from, mid);
 *         leftTask.fork();         // perform about half the work locally
 *         return new FactorialTask(mid + 1, to).compute()
 *                .multiply(leftTask.join());
 *       }
 *     }
 *   }
 *   static BigInteger factorial(int n) { // uses ForkJoinPool.commonPool()
 *     return (n <= 1) ? BigInteger.ONE : new FactorialTask(1, n).invoke();
 *   }
 *   public static void main(String[] args) {
 *     System.out.println(factorial(Integer.parseInt(args[0])));
 *   }
 * }}</pre>
 *
 * @param <V> the type of the result of the task
 *
 * @since 1.7
 * @author Doug Lea
 */
public abstract class RecursiveTask<V> extends ForkJoinTask<V> {
    private static final long serialVersionUID = 5232453952276485270L;

    /**
     * Constructor for subclasses to call.
     */
    public RecursiveTask() {}

    /**
     * The result of the computation.
     */
    @SuppressWarnings("serial") // Conditionally serializable
    V result;

    /**
     * The main computation performed by this task.
     * @return the result of the computation
     */
    protected abstract V compute();

    public final V getRawResult() {
        return result;
    }

    protected final void setRawResult(V value) {
        result = value;
    }

    /**
     * Implements execution conventions for RecursiveTask.
     */
    protected final boolean exec() {
        result = compute();
        return true;
    }

}
