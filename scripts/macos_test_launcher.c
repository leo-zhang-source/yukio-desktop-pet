/* Only for disposable upgrade fixtures, never for a release package.
 * LaunchServices preserves the real HOME even when LSEnvironment requests a
 * different one. Restore the verified fixture home before execing the actual
 * unchanged product executable, so Foundation and Python use the same profile.
 */
#include <mach-o/dyld.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    (void)argc;
    const char *profile = getenv("CFFIXED_USER_HOME");
    const char *token = getenv("YUKIO_UPGRADE_TEST_TOKEN");
    char marker[PATH_MAX], saved[128], executable[PATH_MAX];
    if (!profile || profile[0] != '/' || !token || !*token || strlen(token) >= sizeof(saved))
        return 78;
    if (snprintf(marker, sizeof(marker), "%s/.yukio-upgrade-test-profile", profile) >= (int)sizeof(marker))
        return 78;
    FILE *file = fopen(marker, "r");
    if (!file) return 78;
    size_t bytes = fread(saved, 1, sizeof(saved) - 1, file);
    int extra = fgetc(file);
    int failed = ferror(file); fclose(file); saved[bytes] = '\0';
    if (failed || extra != EOF || bytes != strlen(token) || strcmp(saved, token)) return 78;
    uint32_t size = sizeof(executable);
    if (_NSGetExecutablePath(executable, &size)) return 78;
    char *last = strrchr(executable, '/');
    if (!last || (size_t)(last - executable) + strlen("/YukioPlayer") + 1 > sizeof(executable))
        return 78;
    strcpy(last + 1, "YukioPlayer");
    if (setenv("HOME", profile, 1)) return 78;
    argv[0] = executable;
    execv(executable, argv);
    return 71;
}
