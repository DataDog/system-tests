using System;

namespace weblog.Models.Debugger
{
    public class ExceptionReplayRock : Exception
    {
        public ExceptionReplayRock()
            : base("Rock exception")
        {
        }
    }

    public class ExceptionReplayPaper : Exception
    {
        public ExceptionReplayPaper()
            : base("Paper exception")
        {
        }
    }

    public class ExceptionReplayScissors : Exception
    {
        public ExceptionReplayScissors()
            : base("Scissors exception")
        {
        }
    }
}
