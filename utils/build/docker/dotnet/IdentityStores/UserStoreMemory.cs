using System.Collections.Generic;
using System.Linq;
using System.Security.Claims;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Identity;

namespace weblog.IdentityStores;

public class UserStoreMemory : UserStoreBase<IdentityUser, string, IdentityUserClaim<string>, IdentityUserLogin<string>, IdentityUserToken<string>>
{
    internal static IList<IdentityUser>? AllUsers;

    static UserStoreMemory()
    {
        ResetUsers();
    }

    public UserStoreMemory()
        : base(new IdentityErrorDescriber())
    {
    }

    public static void ResetUsers()
    {
        AllUsers = new List<IdentityUser>
        {
            new("test")
            {
                Id = "social-security-id",
                PasswordHash = "AQAAAAEAACcQAAAAEPvdMCIo7ko3lR7fYZRTQc8jRwb5ziO3FtWS7Z/qfGSNMMIykHRHQNQh0IDBuqANJw==",
                Email = "testuser@ddog.com",
                NormalizedEmail = "TESTUSER@DDOG.COM",
                NormalizedUserName = "TEST",
                SecurityStamp = "PPJ7EANBPPIM25HTJRHDSZVPOBQJMP7Q",
                ConcurrencyStamp = "eeb5d586-783a-4a75-93e3-df74ef4d9f73"
            },
            new("testuuid")
            {
                Id = "591dc126-8431-4d0f-9509-b23318d3dce4",
                PasswordHash = "AQAAAAEAACcQAAAAELVnFN1pQkW9HPEs41hD23e9TFoYHwLWzXBYH8wTsmkjmxKXwI/ROITVYiExp/xdsA==",
                Email = "testuseruuid@ddog.com",
                NormalizedEmail = "TESTUSERUUID@DDOG.COM",
                NormalizedUserName = "TESTUUID",
                SecurityStamp = "PPJ7EANBPPIM25HTJRHDSZVPOBQJMP7Q",
                ConcurrencyStamp = "eeb5d586-783a-4a75-93e3-df74ef4d9f73"
            }
        };
    }

    public override Task AddClaimsAsync(IdentityUser user, IEnumerable<Claim> claims, CancellationToken cancellationToken = new CancellationToken())
    {
        throw new System.NotImplementedException();
    }

    public override Task<IList<Claim>> GetClaimsAsync(IdentityUser user, CancellationToken cancellationToken = new CancellationToken())
    {
        return Task.FromResult<IList<Claim>>(new List<Claim>());
    }

    public override Task<IList<IdentityUser>> GetUsersForClaimAsync(Claim claim, CancellationToken cancellationToken = new CancellationToken())
    {
        throw new System.NotImplementedException();
    }

    public override Task RemoveClaimsAsync(IdentityUser user, IEnumerable<Claim> claims, CancellationToken cancellationToken = new CancellationToken())
    {
        throw new System.NotImplementedException();
    }

    public override Task ReplaceClaimAsync(IdentityUser user, Claim claim, Claim newClaim, CancellationToken cancellationToken = new CancellationToken())
    {
        throw new System.NotImplementedException();
    }

    public override Task RemoveLoginAsync(IdentityUser user, string loginProvider, string providerKey, CancellationToken cancellationToken = new CancellationToken())
    {
        throw new System.NotImplementedException();
    }

    protected override Task RemoveUserTokenAsync(IdentityUserToken<string> token)
    {
        throw new System.NotImplementedException();
    }

    public override Task AddLoginAsync(IdentityUser user, UserLoginInfo login, CancellationToken cancellationToken = new CancellationToken())
    {
        throw new System.NotImplementedException();
    }

    public override Task<IList<UserLoginInfo>> GetLoginsAsync(IdentityUser user, CancellationToken cancellationToken = new CancellationToken())
    {
        throw new System.NotImplementedException();
    }

    protected override Task AddUserTokenAsync(IdentityUserToken<string> token)
    {
        throw new System.NotImplementedException();
    }

    public override Task<IdentityResult> CreateAsync(IdentityUser user, CancellationToken cancellationToken = new CancellationToken())
    {
        AllUsers?.Add(user);
        return Task.FromResult(IdentityResult.Success);
    }

    public override Task<IdentityResult> DeleteAsync(IdentityUser user, CancellationToken cancellationToken = new CancellationToken())
    {
        throw new System.NotImplementedException();
    }

    public override Task<IdentityUser> FindByIdAsync(string userId, CancellationToken cancellationToken = new CancellationToken())
    {
        return Task.FromResult(AllUsers?.FirstOrDefault(u => u.Id == userId))!;
    }

    public override Task<IdentityUser> FindByEmailAsync(string normalizedEmail, CancellationToken cancellationToken = new CancellationToken())
        => Task.FromResult(AllUsers?.FirstOrDefault(u => u.NormalizedEmail == normalizedEmail))!;

    public override Task<IdentityUser> FindByNameAsync(string normalizedUserName, CancellationToken cancellationToken = default) => Task.FromResult(AllUsers?.FirstOrDefault(u => u.NormalizedUserName == normalizedUserName))!;

    public override Task<IdentityResult> UpdateAsync(IdentityUser user, CancellationToken cancellationToken = new CancellationToken())
    {
        if (AllUsers != null)
        {
            var userToUpdate = AllUsers.FirstOrDefault(u => u.Id == user.Id);
            if (userToUpdate != null)
            {
                AllUsers.Remove(userToUpdate);
                AllUsers.Add(user);
                return Task.FromResult(IdentityResult.Success);
            }
        }

        return Task.FromResult(IdentityResult.Failed(new IdentityError { Description = "user did not exist" }));
    }

    public override IQueryable<IdentityUser>? Users { get; }

    protected override Task<IdentityUserToken<string>> FindTokenAsync(IdentityUser user, string loginProvider, string name, CancellationToken cancellationToken)
    {
        throw new System.NotImplementedException();
    }

    protected override Task<IdentityUser> FindUserAsync(string userId, CancellationToken cancellationToken) => Task.FromResult(AllUsers?.FirstOrDefault(u => u.Id == userId))!;

    protected override Task<IdentityUserLogin<string>> FindUserLoginAsync(string loginProvider, string providerKey, CancellationToken cancellationToken)
    {
        throw new System.NotImplementedException();
    }

    protected override Task<IdentityUserLogin<string>> FindUserLoginAsync(string userId, string loginProvider, string providerKey, CancellationToken cancellationToken)
    {
        throw new System.NotImplementedException();
    }
}
