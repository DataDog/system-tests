// CheckStyle: stop header check
// CheckStyle: stop line length check
// GENERATED CONTENT - DO NOT EDIT
// GENERATOR: org.graalvm.compiler.lir.processor.IntrinsicStubProcessor
package com.oracle.svm.graal.stubs;

import org.graalvm.compiler.replacements.nodes.CipherBlockChainingAESNode;
import jdk.vm.ci.code.Architecture;
import org.graalvm.compiler.replacements.nodes.ArrayRegionEqualsWithMaskNode;
import org.graalvm.compiler.replacements.nodes.BigIntegerMulAddNode;
import org.graalvm.compiler.replacements.nodes.EncodeArrayNode;
import com.oracle.svm.graal.RuntimeCPUFeatureRegion;
import org.graalvm.compiler.replacements.StringLatin1InflateNode;
import org.graalvm.compiler.replacements.nodes.AESNode.CryptMode;
import org.graalvm.compiler.replacements.nodes.BigIntegerMultiplyToLenNode;
import org.graalvm.compiler.lir.gen.LIRGeneratorTool.ArrayIndexOfVariant;
import jdk.vm.ci.meta.JavaKind;
import org.graalvm.compiler.replacements.nodes.VectorizedMismatchNode;
import org.graalvm.compiler.replacements.nodes.CalcStringAttributesNode;
import org.graalvm.compiler.replacements.nodes.CountPositivesNode;
import org.graalvm.compiler.replacements.nodes.MessageDigestNode.SHA256Node;
import com.oracle.svm.core.cpufeature.Stubs;
import com.oracle.svm.core.Uninterruptible;
import org.graalvm.compiler.replacements.nodes.MessageDigestNode.MD5Node;
import java.util.EnumSet;
import org.graalvm.compiler.replacements.nodes.GHASHProcessBlocksNode;
import org.graalvm.compiler.lir.gen.LIRGeneratorTool.CalcStringAttributesEncoding;
import org.graalvm.compiler.replacements.nodes.ArrayCompareToNode;
import org.graalvm.compiler.replacements.nodes.MessageDigestNode.SHA1Node;
import org.graalvm.nativeimage.ImageSingletons;
import org.graalvm.compiler.replacements.nodes.ArrayIndexOfNode;
import com.oracle.svm.core.SubstrateTargetDescription;
import org.graalvm.compiler.replacements.nodes.ArrayRegionEqualsNode;
import org.graalvm.compiler.replacements.nodes.AESNode;
import org.graalvm.compiler.replacements.nodes.CounterModeAESNode;
import org.graalvm.compiler.api.replacements.Fold;
import org.graalvm.compiler.replacements.nodes.VectorizedHashCodeNode;
import org.graalvm.compiler.replacements.nodes.ArrayEqualsNode;
import com.oracle.svm.core.snippets.SubstrateForeignCallTarget;
import org.graalvm.compiler.replacements.nodes.BigIntegerSquareToLenNode;
import org.graalvm.compiler.replacements.nodes.MessageDigestNode.SHA512Node;
import org.graalvm.compiler.replacements.nodes.ArrayCopyWithConversionsNode;
import org.graalvm.compiler.core.common.Stride;
import org.graalvm.compiler.debug.GraalError;
import org.graalvm.compiler.replacements.StringUTF16CompressNode;
import org.graalvm.compiler.replacements.nodes.MessageDigestNode.SHA3Node;
import org.graalvm.compiler.replacements.nodes.ArrayRegionCompareToNode;
import org.graalvm.compiler.lir.gen.LIRGeneratorTool.CharsetName;

public class SVMIntrinsicStubsGen{

    @Fold
    public static EnumSet<?> ArrayIndexOfNode_getMinimumFeatures() {
        Architecture arch = ImageSingletons.lookup(SubstrateTargetDescription.class).arch;
        if (arch instanceof jdk.vm.ci.amd64.AMD64) {
            return ArrayIndexOfNode.amd64FeaturesSSE41();
        }
        if (arch instanceof jdk.vm.ci.aarch64.AArch64) {
            return ArrayIndexOfNode.aarch64FeaturesNone();
        }
        throw GraalError.unsupportedArchitecture(arch);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf1S1(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.MatchAny, array, arrayOffset, arrayLength, fromIndex, v1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf1S1RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.MatchAny, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf1S2(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.MatchAny, array, arrayOffset, arrayLength, fromIndex, v1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf1S2RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.MatchAny, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf1S4(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.MatchAny, array, arrayOffset, arrayLength, fromIndex, v1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf1S4RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.MatchAny, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf2S1(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.MatchAny, array, arrayOffset, arrayLength, fromIndex, v1, v2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf2S1RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.MatchAny, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf2S2(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.MatchAny, array, arrayOffset, arrayLength, fromIndex, v1, v2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf2S2RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.MatchAny, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf2S4(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.MatchAny, array, arrayOffset, arrayLength, fromIndex, v1, v2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf2S4RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.MatchAny, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfRange1S1(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.MatchRange, array, arrayOffset, arrayLength, fromIndex, v1, v2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfRange1S1RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.MatchRange, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfRange1S2(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(ArrayIndexOfNode_getMinimumFeatures());
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.MatchRange, ArrayIndexOfNode_getMinimumFeatures(), array, arrayOffset, arrayLength, fromIndex, v1, v2);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfRange1S2RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.MatchRange, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfRange1S4(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(ArrayIndexOfNode_getMinimumFeatures());
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.MatchRange, ArrayIndexOfNode_getMinimumFeatures(), array, arrayOffset, arrayLength, fromIndex, v1, v2);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfRange1S4RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.MatchRange, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfWithMaskS1(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.WithMask, array, arrayOffset, arrayLength, fromIndex, v1, v2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfWithMaskS1RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.WithMask, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfWithMaskS2(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.WithMask, array, arrayOffset, arrayLength, fromIndex, v1, v2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfWithMaskS2RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.WithMask, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfWithMaskS4(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.WithMask, array, arrayOffset, arrayLength, fromIndex, v1, v2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfWithMaskS4RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.WithMask, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTwoConsecutiveS1(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.FindTwoConsecutive, array, arrayOffset, arrayLength, fromIndex, v1, v2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTwoConsecutiveS1RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.FindTwoConsecutive, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTwoConsecutiveS2(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.FindTwoConsecutive, array, arrayOffset, arrayLength, fromIndex, v1, v2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTwoConsecutiveS2RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.FindTwoConsecutive, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTwoConsecutiveS4(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.FindTwoConsecutive, array, arrayOffset, arrayLength, fromIndex, v1, v2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTwoConsecutiveS4RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.FindTwoConsecutive, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf3S1(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.MatchAny, array, arrayOffset, arrayLength, fromIndex, v1, v2, v3);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf3S1RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.MatchAny, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2, v3);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf3S2(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.MatchAny, array, arrayOffset, arrayLength, fromIndex, v1, v2, v3);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf3S2RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.MatchAny, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2, v3);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf3S4(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.MatchAny, array, arrayOffset, arrayLength, fromIndex, v1, v2, v3);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf3S4RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.MatchAny, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2, v3);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf4S1(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.MatchAny, array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf4S1RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.MatchAny, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf4S2(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.MatchAny, array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf4S2RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.MatchAny, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf4S4(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.MatchAny, array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOf4S4RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.MatchAny, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfRange2S1(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.MatchRange, array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfRange2S1RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.MatchRange, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfRange2S2(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(ArrayIndexOfNode_getMinimumFeatures());
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.MatchRange, ArrayIndexOfNode_getMinimumFeatures(), array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfRange2S2RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.MatchRange, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfRange2S4(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(ArrayIndexOfNode_getMinimumFeatures());
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.MatchRange, ArrayIndexOfNode_getMinimumFeatures(), array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfRange2S4RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.MatchRange, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTwoConsecutiveWithMaskS1(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.FindTwoConsecutiveWithMask, array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTwoConsecutiveWithMaskS1RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S1, ArrayIndexOfVariant.FindTwoConsecutiveWithMask, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTwoConsecutiveWithMaskS2(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.FindTwoConsecutiveWithMask, array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTwoConsecutiveWithMaskS2RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S2, ArrayIndexOfVariant.FindTwoConsecutiveWithMask, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTwoConsecutiveWithMaskS4(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.FindTwoConsecutiveWithMask, array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTwoConsecutiveWithMaskS4RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, int v1, int v2, int v3, int v4) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOf(Stride.S4, ArrayIndexOfVariant.FindTwoConsecutiveWithMask, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, v1, v2, v3, v4);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTableS1(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, byte[] tables) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(ArrayIndexOfNode_getMinimumFeatures());
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOfTable(Stride.S1, ArrayIndexOfVariant.Table, ArrayIndexOfNode_getMinimumFeatures(), array, arrayOffset, arrayLength, fromIndex, tables);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTableS1RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, byte[] tables) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOfTable(Stride.S1, ArrayIndexOfVariant.Table, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, tables);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTableS2(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, byte[] tables) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(ArrayIndexOfNode_getMinimumFeatures());
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOfTable(Stride.S2, ArrayIndexOfVariant.Table, ArrayIndexOfNode_getMinimumFeatures(), array, arrayOffset, arrayLength, fromIndex, tables);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTableS2RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, byte[] tables) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOfTable(Stride.S2, ArrayIndexOfVariant.Table, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, tables);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTableS4(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, byte[] tables) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(ArrayIndexOfNode_getMinimumFeatures());
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOfTable(Stride.S4, ArrayIndexOfVariant.Table, ArrayIndexOfNode_getMinimumFeatures(), array, arrayOffset, arrayLength, fromIndex, tables);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int indexOfTableS4RTC(java.lang.Object array, long arrayOffset, int arrayLength, int fromIndex, byte[] tables) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class));
        try {
            return ArrayIndexOfNode.optimizedArrayIndexOfTable(Stride.S4, ArrayIndexOfVariant.Table, Stubs.getRuntimeCheckedCPUFeatures(ArrayIndexOfNode.class), array, arrayOffset, arrayLength, fromIndex, tables);
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean longArraysEquals(org.graalvm.word.Pointer array1, long offset1, org.graalvm.word.Pointer array2, long offset2, int length) {
        return ArrayEqualsNode.equals(array1, offset1, array2, offset2, length, JavaKind.Long);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean longArraysEqualsRTC(org.graalvm.word.Pointer array1, long offset1, org.graalvm.word.Pointer array2, long offset2, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayEqualsNode.class));
        try {
            return ArrayEqualsNode.equals(array1, offset1, array2, offset2, length, JavaKind.Long, Stubs.getRuntimeCheckedCPUFeatures(ArrayEqualsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean floatArraysEquals(org.graalvm.word.Pointer array1, long offset1, org.graalvm.word.Pointer array2, long offset2, int length) {
        return ArrayEqualsNode.equals(array1, offset1, array2, offset2, length, JavaKind.Float);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean floatArraysEqualsRTC(org.graalvm.word.Pointer array1, long offset1, org.graalvm.word.Pointer array2, long offset2, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayEqualsNode.class));
        try {
            return ArrayEqualsNode.equals(array1, offset1, array2, offset2, length, JavaKind.Float, Stubs.getRuntimeCheckedCPUFeatures(ArrayEqualsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean doubleArraysEquals(org.graalvm.word.Pointer array1, long offset1, org.graalvm.word.Pointer array2, long offset2, int length) {
        return ArrayEqualsNode.equals(array1, offset1, array2, offset2, length, JavaKind.Double);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean doubleArraysEqualsRTC(org.graalvm.word.Pointer array1, long offset1, org.graalvm.word.Pointer array2, long offset2, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayEqualsNode.class));
        try {
            return ArrayEqualsNode.equals(array1, offset1, array2, offset2, length, JavaKind.Double, Stubs.getRuntimeCheckedCPUFeatures(ArrayEqualsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS1S1(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S1, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS1S1RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        try {
            return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S1, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS1S2(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S1, Stride.S2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS1S2RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        try {
            return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S1, Stride.S2, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS1S4(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S1, Stride.S4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS1S4RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        try {
            return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S1, Stride.S4, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS2S1(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S2, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS2S1RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        try {
            return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S2, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS2S2(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S2, Stride.S2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS2S2RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        try {
            return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S2, Stride.S2, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS2S4(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S2, Stride.S4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS2S4RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        try {
            return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S2, Stride.S4, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS4S1(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S4, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS4S1RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        try {
            return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S4, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS4S2(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S4, Stride.S2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS4S2RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        try {
            return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S4, Stride.S2, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS4S4(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S4, Stride.S4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsS4S4RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        try {
            return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, Stride.S4, Stride.S4, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsDynamicStrides(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length, int dynamicStrides) {
        return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, dynamicStrides);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsDynamicStridesRTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length, int dynamicStrides) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        try {
            return ArrayRegionEqualsNode.regionEquals(arrayA, offsetA, arrayB, offsetB, length, dynamicStrides, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int byteArrayCompareToByteArray(org.graalvm.word.Pointer arrayA, int lengthA, org.graalvm.word.Pointer arrayB, int lengthB) {
        return ArrayCompareToNode.compareTo(arrayA, lengthA, arrayB, lengthB, Stride.S1, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int byteArrayCompareToByteArrayRTC(org.graalvm.word.Pointer arrayA, int lengthA, org.graalvm.word.Pointer arrayB, int lengthB) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayCompareToNode.class));
        try {
            return ArrayCompareToNode.compareTo(arrayA, lengthA, arrayB, lengthB, Stride.S1, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayCompareToNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int byteArrayCompareToCharArray(org.graalvm.word.Pointer arrayA, int lengthA, org.graalvm.word.Pointer arrayB, int lengthB) {
        return ArrayCompareToNode.compareTo(arrayA, lengthA, arrayB, lengthB, Stride.S1, Stride.S2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int byteArrayCompareToCharArrayRTC(org.graalvm.word.Pointer arrayA, int lengthA, org.graalvm.word.Pointer arrayB, int lengthB) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayCompareToNode.class));
        try {
            return ArrayCompareToNode.compareTo(arrayA, lengthA, arrayB, lengthB, Stride.S1, Stride.S2, Stubs.getRuntimeCheckedCPUFeatures(ArrayCompareToNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int charArrayCompareToByteArray(org.graalvm.word.Pointer arrayA, int lengthA, org.graalvm.word.Pointer arrayB, int lengthB) {
        return ArrayCompareToNode.compareTo(arrayA, lengthA, arrayB, lengthB, Stride.S2, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int charArrayCompareToByteArrayRTC(org.graalvm.word.Pointer arrayA, int lengthA, org.graalvm.word.Pointer arrayB, int lengthB) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayCompareToNode.class));
        try {
            return ArrayCompareToNode.compareTo(arrayA, lengthA, arrayB, lengthB, Stride.S2, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayCompareToNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int charArrayCompareToCharArray(org.graalvm.word.Pointer arrayA, int lengthA, org.graalvm.word.Pointer arrayB, int lengthB) {
        return ArrayCompareToNode.compareTo(arrayA, lengthA, arrayB, lengthB, Stride.S2, Stride.S2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int charArrayCompareToCharArrayRTC(org.graalvm.word.Pointer arrayA, int lengthA, org.graalvm.word.Pointer arrayB, int lengthB) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayCompareToNode.class));
        try {
            return ArrayCompareToNode.compareTo(arrayA, lengthA, arrayB, lengthB, Stride.S2, Stride.S2, Stubs.getRuntimeCheckedCPUFeatures(ArrayCompareToNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS1S1(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S1, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS1S1RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        try {
            return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S1, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS1S2(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S1, Stride.S2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS1S2RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        try {
            return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S1, Stride.S2, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS1S4(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S1, Stride.S4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS1S4RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        try {
            return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S1, Stride.S4, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS2S1(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S2, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS2S1RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        try {
            return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S2, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS2S2(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S2, Stride.S2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS2S2RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        try {
            return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S2, Stride.S2, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS2S4(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S2, Stride.S4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS2S4RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        try {
            return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S2, Stride.S4, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS4S1(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S4, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS4S1RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        try {
            return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S4, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS4S2(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S4, Stride.S2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS4S2RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        try {
            return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S4, Stride.S2, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS4S4(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S4, Stride.S4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToS4S4RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        try {
            return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, Stride.S4, Stride.S4, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToDynamicStrides(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length, int dynamicStrides) {
        return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, dynamicStrides);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int arrayRegionCompareToDynamicStridesRTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, int length, int dynamicStrides) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        try {
            return ArrayRegionCompareToNode.compare(arrayA, offsetA, arrayB, offsetB, length, dynamicStrides, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionCompareToNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS1S1(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S1, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS1S1RTC(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        try {
            ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S1, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS1S2(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S1, Stride.S2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS1S2RTC(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        try {
            ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S1, Stride.S2, Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS1S4(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S1, Stride.S4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS1S4RTC(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        try {
            ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S1, Stride.S4, Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS2S1(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S2, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS2S1RTC(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        try {
            ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S2, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS2S2(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S2, Stride.S2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS2S2RTC(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        try {
            ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S2, Stride.S2, Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS2S4(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S2, Stride.S4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS2S4RTC(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        try {
            ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S2, Stride.S4, Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS4S1(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S4, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS4S1RTC(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        try {
            ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S4, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS4S2(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S4, Stride.S2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS4S2RTC(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        try {
            ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S4, Stride.S2, Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS4S4(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S4, Stride.S4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsS4S4RTC(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        try {
            ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, Stride.S4, Stride.S4, Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsDynamicStrides(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length, int stride) {
        ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, stride);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void arrayCopyWithConversionsDynamicStridesRTC(java.lang.Object arraySrc, long offsetSrc, java.lang.Object arrayDst, long offsetDst, int length, int stride) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        try {
            ArrayCopyWithConversionsNode.arrayCopy(arraySrc, offsetSrc, arrayDst, offsetDst, length, stride, Stubs.getRuntimeCheckedCPUFeatures(ArrayCopyWithConversionsNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int stringUTF16Compress(org.graalvm.word.Pointer src, org.graalvm.word.Pointer dst, int len) {
        return StringUTF16CompressNode.stringUTF16Compress(src, dst, len);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int stringUTF16CompressRTC(org.graalvm.word.Pointer src, org.graalvm.word.Pointer dst, int len) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(StringUTF16CompressNode.class));
        try {
            return StringUTF16CompressNode.stringUTF16Compress(src, dst, len, Stubs.getRuntimeCheckedCPUFeatures(StringUTF16CompressNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void stringLatin1Inflate(org.graalvm.word.Pointer src, org.graalvm.word.Pointer dst, int len) {
        StringLatin1InflateNode.stringLatin1Inflate(src, dst, len);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void stringLatin1InflateRTC(org.graalvm.word.Pointer src, org.graalvm.word.Pointer dst, int len) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(StringLatin1InflateNode.class));
        try {
            StringLatin1InflateNode.stringLatin1Inflate(src, dst, len, Stubs.getRuntimeCheckedCPUFeatures(StringLatin1InflateNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int stringCodingCountPositives(org.graalvm.word.Pointer array, int len) {
        return CountPositivesNode.stringCodingCountPositives(array, len);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int stringCodingCountPositivesRTC(org.graalvm.word.Pointer array, int len) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(CountPositivesNode.class));
        try {
            return CountPositivesNode.stringCodingCountPositives(array, len, Stubs.getRuntimeCheckedCPUFeatures(CountPositivesNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int stringCodingEncodeArrayAscii(org.graalvm.word.Pointer src, org.graalvm.word.Pointer dst, int len) {
        return EncodeArrayNode.stringCodingEncodeArray(src, dst, len, CharsetName.ASCII);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int stringCodingEncodeArrayAsciiRTC(org.graalvm.word.Pointer src, org.graalvm.word.Pointer dst, int len) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(EncodeArrayNode.class));
        try {
            return EncodeArrayNode.stringCodingEncodeArray(src, dst, len, CharsetName.ASCII, Stubs.getRuntimeCheckedCPUFeatures(EncodeArrayNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int stringCodingEncodeArrayLatin1(org.graalvm.word.Pointer src, org.graalvm.word.Pointer dst, int len) {
        return EncodeArrayNode.stringCodingEncodeArray(src, dst, len, CharsetName.ISO_8859_1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int stringCodingEncodeArrayLatin1RTC(org.graalvm.word.Pointer src, org.graalvm.word.Pointer dst, int len) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(EncodeArrayNode.class));
        try {
            return EncodeArrayNode.stringCodingEncodeArray(src, dst, len, CharsetName.ISO_8859_1, Stubs.getRuntimeCheckedCPUFeatures(EncodeArrayNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int vectorizedMismatch(org.graalvm.word.Pointer arrayA, org.graalvm.word.Pointer arrayB, int length, int stride) {
        return VectorizedMismatchNode.vectorizedMismatch(arrayA, arrayB, length, stride);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int vectorizedMismatchRTC(org.graalvm.word.Pointer arrayA, org.graalvm.word.Pointer arrayB, int length, int stride) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(VectorizedMismatchNode.class));
        try {
            return VectorizedMismatchNode.vectorizedMismatch(arrayA, arrayB, length, stride, Stubs.getRuntimeCheckedCPUFeatures(VectorizedMismatchNode.class));
        } finally {
            region.leave();
        }
    }

    @Fold
    public static EnumSet<?> VectorizedHashCodeNode_getMinimumFeatures() {
        Architecture arch = ImageSingletons.lookup(SubstrateTargetDescription.class).arch;
        if (arch instanceof jdk.vm.ci.amd64.AMD64) {
            return VectorizedHashCodeNode.minFeaturesAMD64();
        }
        if (arch instanceof jdk.vm.ci.aarch64.AArch64) {
            throw GraalError.shouldNotReachHere("not implemented");
        }
        throw GraalError.unsupportedArchitecture(arch);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int vectorizedHashCodeBoolean(org.graalvm.word.Pointer arrayStart, int length, int initialValue) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(VectorizedHashCodeNode_getMinimumFeatures());
        try {
            return VectorizedHashCodeNode.vectorizedHashCode(arrayStart, length, initialValue, JavaKind.Boolean, VectorizedHashCodeNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int vectorizedHashCodeBooleanRTC(org.graalvm.word.Pointer arrayStart, int length, int initialValue) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(VectorizedHashCodeNode.class));
        try {
            return VectorizedHashCodeNode.vectorizedHashCode(arrayStart, length, initialValue, JavaKind.Boolean, Stubs.getRuntimeCheckedCPUFeatures(VectorizedHashCodeNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int vectorizedHashCodeChar(org.graalvm.word.Pointer arrayStart, int length, int initialValue) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(VectorizedHashCodeNode_getMinimumFeatures());
        try {
            return VectorizedHashCodeNode.vectorizedHashCode(arrayStart, length, initialValue, JavaKind.Char, VectorizedHashCodeNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int vectorizedHashCodeCharRTC(org.graalvm.word.Pointer arrayStart, int length, int initialValue) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(VectorizedHashCodeNode.class));
        try {
            return VectorizedHashCodeNode.vectorizedHashCode(arrayStart, length, initialValue, JavaKind.Char, Stubs.getRuntimeCheckedCPUFeatures(VectorizedHashCodeNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int vectorizedHashCodeByte(org.graalvm.word.Pointer arrayStart, int length, int initialValue) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(VectorizedHashCodeNode_getMinimumFeatures());
        try {
            return VectorizedHashCodeNode.vectorizedHashCode(arrayStart, length, initialValue, JavaKind.Byte, VectorizedHashCodeNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int vectorizedHashCodeByteRTC(org.graalvm.word.Pointer arrayStart, int length, int initialValue) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(VectorizedHashCodeNode.class));
        try {
            return VectorizedHashCodeNode.vectorizedHashCode(arrayStart, length, initialValue, JavaKind.Byte, Stubs.getRuntimeCheckedCPUFeatures(VectorizedHashCodeNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int vectorizedHashCodeShort(org.graalvm.word.Pointer arrayStart, int length, int initialValue) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(VectorizedHashCodeNode_getMinimumFeatures());
        try {
            return VectorizedHashCodeNode.vectorizedHashCode(arrayStart, length, initialValue, JavaKind.Short, VectorizedHashCodeNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int vectorizedHashCodeShortRTC(org.graalvm.word.Pointer arrayStart, int length, int initialValue) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(VectorizedHashCodeNode.class));
        try {
            return VectorizedHashCodeNode.vectorizedHashCode(arrayStart, length, initialValue, JavaKind.Short, Stubs.getRuntimeCheckedCPUFeatures(VectorizedHashCodeNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int vectorizedHashCodeInt(org.graalvm.word.Pointer arrayStart, int length, int initialValue) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(VectorizedHashCodeNode_getMinimumFeatures());
        try {
            return VectorizedHashCodeNode.vectorizedHashCode(arrayStart, length, initialValue, JavaKind.Int, VectorizedHashCodeNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int vectorizedHashCodeIntRTC(org.graalvm.word.Pointer arrayStart, int length, int initialValue) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(VectorizedHashCodeNode.class));
        try {
            return VectorizedHashCodeNode.vectorizedHashCode(arrayStart, length, initialValue, JavaKind.Int, Stubs.getRuntimeCheckedCPUFeatures(VectorizedHashCodeNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS1S2S1(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S1, Stride.S2, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS1S2S1RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        try {
            return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S1, Stride.S2, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS2S2S1(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S2, Stride.S2, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS2S2S1RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        try {
            return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S2, Stride.S2, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS1S1(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S1, Stride.S1, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS1S1RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        try {
            return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S1, Stride.S1, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS1S2(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S1, Stride.S2, Stride.S2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS1S2RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        try {
            return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S1, Stride.S2, Stride.S2, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS1S4(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S1, Stride.S4, Stride.S4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS1S4RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        try {
            return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S1, Stride.S4, Stride.S4, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS2S1(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S2, Stride.S1, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS2S1RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        try {
            return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S2, Stride.S1, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS2S2(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S2, Stride.S2, Stride.S2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS2S2RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        try {
            return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S2, Stride.S2, Stride.S2, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS2S4(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S2, Stride.S4, Stride.S4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS2S4RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        try {
            return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S2, Stride.S4, Stride.S4, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS4S1(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S4, Stride.S1, Stride.S1);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS4S1RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        try {
            return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S4, Stride.S1, Stride.S1, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS4S2(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S4, Stride.S2, Stride.S2);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS4S2RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        try {
            return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S4, Stride.S2, Stride.S2, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS4S4(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S4, Stride.S4, Stride.S4);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskS4S4RTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        try {
            return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, Stride.S4, Stride.S4, Stride.S4, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskDynamicStrides(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length, int stride) {
        return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, stride);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static boolean arrayRegionEqualsWithMaskDynamicStridesRTC(java.lang.Object arrayA, long offsetA, java.lang.Object arrayB, long offsetB, org.graalvm.word.Pointer mask, int length, int stride) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        try {
            return ArrayRegionEqualsWithMaskNode.regionEquals(arrayA, offsetA, arrayB, offsetB, mask, length, stride, Stubs.getRuntimeCheckedCPUFeatures(ArrayRegionEqualsWithMaskNode.class));
        } finally {
            region.leave();
        }
    }

    @Fold
    public static EnumSet<?> CalcStringAttributesNode_getMinimumFeatures() {
        Architecture arch = ImageSingletons.lookup(SubstrateTargetDescription.class).arch;
        if (arch instanceof jdk.vm.ci.amd64.AMD64) {
            return CalcStringAttributesNode.minFeaturesAMD64();
        }
        if (arch instanceof jdk.vm.ci.aarch64.AArch64) {
            return CalcStringAttributesNode.minFeaturesAARCH64();
        }
        throw GraalError.unsupportedArchitecture(arch);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int calcStringAttributesLatin1(java.lang.Object array, long offset, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(CalcStringAttributesNode_getMinimumFeatures());
        try {
            return CalcStringAttributesNode.intReturnValue(array, offset, length, CalcStringAttributesEncoding.LATIN1, false, CalcStringAttributesNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int calcStringAttributesLatin1RTC(java.lang.Object array, long offset, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(CalcStringAttributesNode.class));
        try {
            return CalcStringAttributesNode.intReturnValue(array, offset, length, CalcStringAttributesEncoding.LATIN1, false, Stubs.getRuntimeCheckedCPUFeatures(CalcStringAttributesNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int calcStringAttributesBMP(java.lang.Object array, long offset, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(CalcStringAttributesNode_getMinimumFeatures());
        try {
            return CalcStringAttributesNode.intReturnValue(array, offset, length, CalcStringAttributesEncoding.BMP, false, CalcStringAttributesNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int calcStringAttributesBMPRTC(java.lang.Object array, long offset, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(CalcStringAttributesNode.class));
        try {
            return CalcStringAttributesNode.intReturnValue(array, offset, length, CalcStringAttributesEncoding.BMP, false, Stubs.getRuntimeCheckedCPUFeatures(CalcStringAttributesNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int calcStringAttributesUTF32(java.lang.Object array, long offset, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(CalcStringAttributesNode_getMinimumFeatures());
        try {
            return CalcStringAttributesNode.intReturnValue(array, offset, length, CalcStringAttributesEncoding.UTF_32, false, CalcStringAttributesNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int calcStringAttributesUTF32RTC(java.lang.Object array, long offset, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(CalcStringAttributesNode.class));
        try {
            return CalcStringAttributesNode.intReturnValue(array, offset, length, CalcStringAttributesEncoding.UTF_32, false, Stubs.getRuntimeCheckedCPUFeatures(CalcStringAttributesNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static long calcStringAttributesUTF8Valid(java.lang.Object array, long offset, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(CalcStringAttributesNode_getMinimumFeatures());
        try {
            return CalcStringAttributesNode.longReturnValue(array, offset, length, CalcStringAttributesEncoding.UTF_8, true, CalcStringAttributesNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static long calcStringAttributesUTF8ValidRTC(java.lang.Object array, long offset, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(CalcStringAttributesNode.class));
        try {
            return CalcStringAttributesNode.longReturnValue(array, offset, length, CalcStringAttributesEncoding.UTF_8, true, Stubs.getRuntimeCheckedCPUFeatures(CalcStringAttributesNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static long calcStringAttributesUTF8Unknown(java.lang.Object array, long offset, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(CalcStringAttributesNode_getMinimumFeatures());
        try {
            return CalcStringAttributesNode.longReturnValue(array, offset, length, CalcStringAttributesEncoding.UTF_8, false, CalcStringAttributesNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static long calcStringAttributesUTF8UnknownRTC(java.lang.Object array, long offset, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(CalcStringAttributesNode.class));
        try {
            return CalcStringAttributesNode.longReturnValue(array, offset, length, CalcStringAttributesEncoding.UTF_8, false, Stubs.getRuntimeCheckedCPUFeatures(CalcStringAttributesNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static long calcStringAttributesUTF16Valid(java.lang.Object array, long offset, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(CalcStringAttributesNode_getMinimumFeatures());
        try {
            return CalcStringAttributesNode.longReturnValue(array, offset, length, CalcStringAttributesEncoding.UTF_16, true, CalcStringAttributesNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static long calcStringAttributesUTF16ValidRTC(java.lang.Object array, long offset, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(CalcStringAttributesNode.class));
        try {
            return CalcStringAttributesNode.longReturnValue(array, offset, length, CalcStringAttributesEncoding.UTF_16, true, Stubs.getRuntimeCheckedCPUFeatures(CalcStringAttributesNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static long calcStringAttributesUTF16Unknown(java.lang.Object array, long offset, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(CalcStringAttributesNode_getMinimumFeatures());
        try {
            return CalcStringAttributesNode.longReturnValue(array, offset, length, CalcStringAttributesEncoding.UTF_16, false, CalcStringAttributesNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static long calcStringAttributesUTF16UnknownRTC(java.lang.Object array, long offset, int length) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(CalcStringAttributesNode.class));
        try {
            return CalcStringAttributesNode.longReturnValue(array, offset, length, CalcStringAttributesEncoding.UTF_16, false, Stubs.getRuntimeCheckedCPUFeatures(CalcStringAttributesNode.class));
        } finally {
            region.leave();
        }
    }

    @Fold
    public static EnumSet<?> AESNode_getMinimumFeatures() {
        Architecture arch = ImageSingletons.lookup(SubstrateTargetDescription.class).arch;
        if (arch instanceof jdk.vm.ci.amd64.AMD64) {
            return AESNode.minFeaturesAMD64();
        }
        if (arch instanceof jdk.vm.ci.aarch64.AArch64) {
            return AESNode.minFeaturesAARCH64();
        }
        throw GraalError.unsupportedArchitecture(arch);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void aesEncrypt(org.graalvm.word.Pointer from, org.graalvm.word.Pointer to, org.graalvm.word.Pointer key) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(AESNode_getMinimumFeatures());
        try {
            AESNode.apply(from, to, key, CryptMode.ENCRYPT, AESNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void aesEncryptRTC(org.graalvm.word.Pointer from, org.graalvm.word.Pointer to, org.graalvm.word.Pointer key) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(AESNode.class));
        try {
            AESNode.apply(from, to, key, CryptMode.ENCRYPT, Stubs.getRuntimeCheckedCPUFeatures(AESNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void aesDecrypt(org.graalvm.word.Pointer from, org.graalvm.word.Pointer to, org.graalvm.word.Pointer key) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(AESNode_getMinimumFeatures());
        try {
            AESNode.apply(from, to, key, CryptMode.DECRYPT, AESNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void aesDecryptRTC(org.graalvm.word.Pointer from, org.graalvm.word.Pointer to, org.graalvm.word.Pointer key) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(AESNode.class));
        try {
            AESNode.apply(from, to, key, CryptMode.DECRYPT, Stubs.getRuntimeCheckedCPUFeatures(AESNode.class));
        } finally {
            region.leave();
        }
    }

    @Fold
    public static EnumSet<?> CounterModeAESNode_getMinimumFeatures() {
        Architecture arch = ImageSingletons.lookup(SubstrateTargetDescription.class).arch;
        if (arch instanceof jdk.vm.ci.amd64.AMD64) {
            return CounterModeAESNode.minFeaturesAMD64();
        }
        if (arch instanceof jdk.vm.ci.aarch64.AArch64) {
            return CounterModeAESNode.minFeaturesAARCH64();
        }
        throw GraalError.unsupportedArchitecture(arch);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int ctrAESCrypt(org.graalvm.word.Pointer inAddr, org.graalvm.word.Pointer outAddr, org.graalvm.word.Pointer kAddr, org.graalvm.word.Pointer counterAddr, int len, org.graalvm.word.Pointer encryptedCounterAddr, org.graalvm.word.Pointer usedPtr) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(CounterModeAESNode_getMinimumFeatures());
        try {
            return CounterModeAESNode.apply(inAddr, outAddr, kAddr, counterAddr, len, encryptedCounterAddr, usedPtr, CounterModeAESNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int ctrAESCryptRTC(org.graalvm.word.Pointer inAddr, org.graalvm.word.Pointer outAddr, org.graalvm.word.Pointer kAddr, org.graalvm.word.Pointer counterAddr, int len, org.graalvm.word.Pointer encryptedCounterAddr, org.graalvm.word.Pointer usedPtr) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(CounterModeAESNode.class));
        try {
            return CounterModeAESNode.apply(inAddr, outAddr, kAddr, counterAddr, len, encryptedCounterAddr, usedPtr, Stubs.getRuntimeCheckedCPUFeatures(CounterModeAESNode.class));
        } finally {
            region.leave();
        }
    }

    @Fold
    public static EnumSet<?> CipherBlockChainingAESNode_getMinimumFeatures() {
        Architecture arch = ImageSingletons.lookup(SubstrateTargetDescription.class).arch;
        if (arch instanceof jdk.vm.ci.amd64.AMD64) {
            return CipherBlockChainingAESNode.minFeaturesAMD64();
        }
        if (arch instanceof jdk.vm.ci.aarch64.AArch64) {
            return CipherBlockChainingAESNode.minFeaturesAARCH64();
        }
        throw GraalError.unsupportedArchitecture(arch);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int cbcAESEncrypt(org.graalvm.word.Pointer from, org.graalvm.word.Pointer to, org.graalvm.word.Pointer key, org.graalvm.word.Pointer r, int len) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(CipherBlockChainingAESNode_getMinimumFeatures());
        try {
            return CipherBlockChainingAESNode.apply(from, to, key, r, len, CryptMode.ENCRYPT, CipherBlockChainingAESNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int cbcAESEncryptRTC(org.graalvm.word.Pointer from, org.graalvm.word.Pointer to, org.graalvm.word.Pointer key, org.graalvm.word.Pointer r, int len) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(CipherBlockChainingAESNode.class));
        try {
            return CipherBlockChainingAESNode.apply(from, to, key, r, len, CryptMode.ENCRYPT, Stubs.getRuntimeCheckedCPUFeatures(CipherBlockChainingAESNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int cbcAESDecrypt(org.graalvm.word.Pointer from, org.graalvm.word.Pointer to, org.graalvm.word.Pointer key, org.graalvm.word.Pointer r, int len) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(CipherBlockChainingAESNode_getMinimumFeatures());
        try {
            return CipherBlockChainingAESNode.apply(from, to, key, r, len, CryptMode.DECRYPT, CipherBlockChainingAESNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int cbcAESDecryptRTC(org.graalvm.word.Pointer from, org.graalvm.word.Pointer to, org.graalvm.word.Pointer key, org.graalvm.word.Pointer r, int len) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(CipherBlockChainingAESNode.class));
        try {
            return CipherBlockChainingAESNode.apply(from, to, key, r, len, CryptMode.DECRYPT, Stubs.getRuntimeCheckedCPUFeatures(CipherBlockChainingAESNode.class));
        } finally {
            region.leave();
        }
    }

    @Fold
    public static EnumSet<?> GHASHProcessBlocksNode_getMinimumFeatures() {
        Architecture arch = ImageSingletons.lookup(SubstrateTargetDescription.class).arch;
        if (arch instanceof jdk.vm.ci.amd64.AMD64) {
            return GHASHProcessBlocksNode.minFeaturesAMD64();
        }
        if (arch instanceof jdk.vm.ci.aarch64.AArch64) {
            return GHASHProcessBlocksNode.minFeaturesAARCH64();
        }
        throw GraalError.unsupportedArchitecture(arch);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void ghashProcessBlocks(org.graalvm.word.Pointer state, org.graalvm.word.Pointer hashSubkey, org.graalvm.word.Pointer data, int blocks) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(GHASHProcessBlocksNode_getMinimumFeatures());
        try {
            GHASHProcessBlocksNode.apply(state, hashSubkey, data, blocks, GHASHProcessBlocksNode_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void ghashProcessBlocksRTC(org.graalvm.word.Pointer state, org.graalvm.word.Pointer hashSubkey, org.graalvm.word.Pointer data, int blocks) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(GHASHProcessBlocksNode.class));
        try {
            GHASHProcessBlocksNode.apply(state, hashSubkey, data, blocks, Stubs.getRuntimeCheckedCPUFeatures(GHASHProcessBlocksNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void multiplyToLen(org.graalvm.word.Pointer x, int xlen, org.graalvm.word.Pointer y, int ylen, org.graalvm.word.Pointer z, int zlen) {
        BigIntegerMultiplyToLenNode.apply(x, xlen, y, ylen, z, zlen);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void multiplyToLenRTC(org.graalvm.word.Pointer x, int xlen, org.graalvm.word.Pointer y, int ylen, org.graalvm.word.Pointer z, int zlen) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(BigIntegerMultiplyToLenNode.class));
        try {
            BigIntegerMultiplyToLenNode.apply(x, xlen, y, ylen, z, zlen, Stubs.getRuntimeCheckedCPUFeatures(BigIntegerMultiplyToLenNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int mulAdd(org.graalvm.word.Pointer out, org.graalvm.word.Pointer in, int offset, int len, int k) {
        return BigIntegerMulAddNode.apply(out, in, offset, len, k);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static int mulAddRTC(org.graalvm.word.Pointer out, org.graalvm.word.Pointer in, int offset, int len, int k) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(BigIntegerMulAddNode.class));
        try {
            return BigIntegerMulAddNode.apply(out, in, offset, len, k, Stubs.getRuntimeCheckedCPUFeatures(BigIntegerMulAddNode.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void squareToLen(org.graalvm.word.Pointer x, int len, org.graalvm.word.Pointer z, int zlen) {
        BigIntegerSquareToLenNode.apply(x, len, z, zlen);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void squareToLenRTC(org.graalvm.word.Pointer x, int len, org.graalvm.word.Pointer z, int zlen) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(BigIntegerSquareToLenNode.class));
        try {
            BigIntegerSquareToLenNode.apply(x, len, z, zlen, Stubs.getRuntimeCheckedCPUFeatures(BigIntegerSquareToLenNode.class));
        } finally {
            region.leave();
        }
    }

    @Fold
    public static EnumSet<?> SHA1Node_getMinimumFeatures() {
        Architecture arch = ImageSingletons.lookup(SubstrateTargetDescription.class).arch;
        if (arch instanceof jdk.vm.ci.amd64.AMD64) {
            return SHA1Node.minFeaturesAMD64();
        }
        if (arch instanceof jdk.vm.ci.aarch64.AArch64) {
            return SHA1Node.minFeaturesAARCH64();
        }
        throw GraalError.unsupportedArchitecture(arch);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void sha1ImplCompress(org.graalvm.word.Pointer buf, org.graalvm.word.Pointer state) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(SHA1Node_getMinimumFeatures());
        try {
            SHA1Node.sha1ImplCompress(buf, state, SHA1Node_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void sha1ImplCompressRTC(org.graalvm.word.Pointer buf, org.graalvm.word.Pointer state) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(SHA1Node.class));
        try {
            SHA1Node.sha1ImplCompress(buf, state, Stubs.getRuntimeCheckedCPUFeatures(SHA1Node.class));
        } finally {
            region.leave();
        }
    }

    @Fold
    public static EnumSet<?> SHA256Node_getMinimumFeatures() {
        Architecture arch = ImageSingletons.lookup(SubstrateTargetDescription.class).arch;
        if (arch instanceof jdk.vm.ci.amd64.AMD64) {
            return SHA256Node.minFeaturesAMD64();
        }
        if (arch instanceof jdk.vm.ci.aarch64.AArch64) {
            return SHA256Node.minFeaturesAARCH64();
        }
        throw GraalError.unsupportedArchitecture(arch);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void sha256ImplCompress(org.graalvm.word.Pointer buf, org.graalvm.word.Pointer state) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(SHA256Node_getMinimumFeatures());
        try {
            SHA256Node.sha256ImplCompress(buf, state, SHA256Node_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void sha256ImplCompressRTC(org.graalvm.word.Pointer buf, org.graalvm.word.Pointer state) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(SHA256Node.class));
        try {
            SHA256Node.sha256ImplCompress(buf, state, Stubs.getRuntimeCheckedCPUFeatures(SHA256Node.class));
        } finally {
            region.leave();
        }
    }

    @Fold
    public static EnumSet<?> SHA3Node_getMinimumFeatures() {
        Architecture arch = ImageSingletons.lookup(SubstrateTargetDescription.class).arch;
        if (arch instanceof jdk.vm.ci.amd64.AMD64) {
            throw GraalError.shouldNotReachHere("not implemented");
        }
        if (arch instanceof jdk.vm.ci.aarch64.AArch64) {
            return SHA3Node.minFeaturesAARCH64();
        }
        throw GraalError.unsupportedArchitecture(arch);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void sha3ImplCompress(org.graalvm.word.Pointer buf, org.graalvm.word.Pointer state, int blockSize) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(SHA3Node_getMinimumFeatures());
        try {
            SHA3Node.sha3ImplCompress(buf, state, blockSize, SHA3Node_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void sha3ImplCompressRTC(org.graalvm.word.Pointer buf, org.graalvm.word.Pointer state, int blockSize) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(SHA3Node.class));
        try {
            SHA3Node.sha3ImplCompress(buf, state, blockSize, Stubs.getRuntimeCheckedCPUFeatures(SHA3Node.class));
        } finally {
            region.leave();
        }
    }

    @Fold
    public static EnumSet<?> SHA512Node_getMinimumFeatures() {
        Architecture arch = ImageSingletons.lookup(SubstrateTargetDescription.class).arch;
        if (arch instanceof jdk.vm.ci.amd64.AMD64) {
            return SHA512Node.minFeaturesAMD64();
        }
        if (arch instanceof jdk.vm.ci.aarch64.AArch64) {
            return SHA512Node.minFeaturesAARCH64();
        }
        throw GraalError.unsupportedArchitecture(arch);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void sha512ImplCompress(org.graalvm.word.Pointer buf, org.graalvm.word.Pointer state) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(SHA512Node_getMinimumFeatures());
        try {
            SHA512Node.sha512ImplCompress(buf, state, SHA512Node_getMinimumFeatures());
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void sha512ImplCompressRTC(org.graalvm.word.Pointer buf, org.graalvm.word.Pointer state) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(SHA512Node.class));
        try {
            SHA512Node.sha512ImplCompress(buf, state, Stubs.getRuntimeCheckedCPUFeatures(SHA512Node.class));
        } finally {
            region.leave();
        }
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void md5ImplCompress(org.graalvm.word.Pointer buf, org.graalvm.word.Pointer state) {
        MD5Node.md5ImplCompress(buf, state);
    }

    @Uninterruptible(reason = "Must not do a safepoint check.")
    @SubstrateForeignCallTarget(stubCallingConvention = false, fullyUninterruptible = true)
    private static void md5ImplCompressRTC(org.graalvm.word.Pointer buf, org.graalvm.word.Pointer state) {
        RuntimeCPUFeatureRegion region = RuntimeCPUFeatureRegion.enterSet(Stubs.getRuntimeCheckedCPUFeatures(MD5Node.class));
        try {
            MD5Node.md5ImplCompress(buf, state, Stubs.getRuntimeCheckedCPUFeatures(MD5Node.class));
        } finally {
            region.leave();
        }
    }

}
