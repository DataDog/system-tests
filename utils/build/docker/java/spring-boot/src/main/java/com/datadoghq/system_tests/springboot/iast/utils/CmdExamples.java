package com.datadoghq.system_tests.springboot.iast.utils;

import org.springframework.core.task.TaskExecutor;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.io.StringWriter;

@Component
public class CmdExamples {

    private final TaskExecutor taskExecutor;

    public CmdExamples(final TaskExecutor taskExecutor) {
        this.taskExecutor = taskExecutor;
    }

    public String insecureCmd(final String... cmd) {
        return withProcess(() -> Runtime.getRuntime().exec(cmd));
    }

    private String withProcess(final Operation<Process> op) {
        final StringBuilder result = new StringBuilder();
        Process process = null;
        try {
            process = op.run();
            final Process finalProcess = process;
            taskExecutor.execute(() -> reapOutput(result, finalProcess));
        } catch (final Throwable e) {
            // ignore it
        } finally {
            if (process != null && process.isAlive()) {
                process.destroyForcibly();
            }
        }
        return result.toString();
    }

    private void reapOutput(final StringBuilder builder, final Process process) {
        try (final BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
            while (process.isAlive()) {
                final String line = reader.readLine();
                if (line != null) {
                    builder.append(line);
                }
            }
        } catch (IOException e) {
            final StringWriter writer = new StringWriter();
            e.printStackTrace(new PrintWriter(writer));
            builder.append(writer);
        }
    }

    private interface Operation<E> {
        E run() throws Throwable;
    }
}
