using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Formatters;
using Microsoft.AspNetCore.Mvc.ModelBinding;
using Microsoft.AspNetCore.Mvc.ModelBinding.Binders;
using Microsoft.AspNetCore.Routing;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Threading.Tasks;

namespace weblog
{
    [ApiController]
    [Route("iast")]
    public class IastController : Controller
    {
        [HttpGet("insecure_hashing/test_md5_algorithm")]
        public IActionResult test_md5_algorithm(string user)
        {
            var byteArg = new byte[] { 3, 5, 6 };
            var result = MD5.Create().ComputeHash(byteArg);
			return Content(result.ToString());
        }

        [HttpGet("insecure_hashing/test_secure_algorithm")]
        public IActionResult test_secure_algorithm(string user)
        {
            var byteArg = new byte[] { 3, 5, 6 };
            var result = SHA256.Create().ComputeHash(byteArg);
			return Content(result.ToString());
        }


        [HttpGet("insecure_hashing/multiple_hash")]
        public IActionResult multiple_hash(string user)
        {
            var byteArg = new byte[] { 3, 5, 6 };
            var result = MD5.Create().ComputeHash(byteArg);
			_ = GetSHA1(byteArg);
			return Content(result.ToString());
        }
		
		private byte[] GetSHA1(byte[] array)
		{
			return SHA1.Create().ComputeHash(array);
		}
		
        [HttpGet("insecure_hashing/deduplicate")]
        public IActionResult deduplicate(string user)
        {
            var byteArg = new byte[] { 3, 5, 6 };
			
			byte[] result = null;
			for (int i = 0; i < 10; i++)
			{
				result = MD5.Create().ComputeHash(byteArg);
			}
			
			return Content(result.ToString());
        }
    }
}