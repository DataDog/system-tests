#!/bin/bash

cursor-agent -p "@promptfoo-llm.mdc Run the complete test suite." 
claude --permission-mode acceptEdits -p "@promptfoo-llm.mdc Run the complete test suite."
promptfoo eval --no-cache