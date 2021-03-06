from typing import Any
from typing import Optional

from bugswarm.common import credentials
from .step import Step
from bugswarm.common import log
from bugswarm.common import github_wrapper


class GetBuildSystemInfo(Step):
    """
    This step will get the build system info (Maven, Gradle, Ant).
    Ref: https://stackoverflow.com/questions/25022016/get-all-file-names-from-a-github-repo-through-the-github-api
    """
    def __init__(self):
        self.git_wrapper = github_wrapper.GitHubWrapper(credentials.GITHUB_TOKENS)

    def process(self, data: Any, context: dict) -> Optional[Any]:
        log.info('Getting build system info.')
        branches = data
        repo = context['repo']

        for _, branch_obj in branches.items():
            if not branch_obj.pairs:
                continue
            for pair in branch_obj.pairs:
                failed_build_commit_sha = pair.failed_build.commit
                passed_build_commit_sha = pair.passed_build.commit

                failed_build_info = self.get_build_info_from_github_api(repo, failed_build_commit_sha)
                passed_build_info = self.get_build_info_from_github_api(repo, passed_build_commit_sha)
                if failed_build_info == -1 or passed_build_info == -1:
                    continue

                if failed_build_info != passed_build_info:
                    failed_build_info = 'NA'
                jobpairs = pair.jobpairs
                for jp in jobpairs:
                    jp.build_system = failed_build_info
        return data

    def get_build_info_from_github_api(self, repo, build_commit_sha):
        # e.g. https://api.github.com/repos/python/mypy/git/commits/4eff613a6c96579d11dad72e63200b74afc39433
        url = 'https://api.github.com/repos/{}/git/commits/{}'.format(repo, build_commit_sha)

        status, json_data = self.git_wrapper.get(url)
        try:
            if status is None or not status.ok:
                log.info('commit: {} not available on github. Skipping'.format(build_commit_sha))
                return -1

            # e.g. https://api.github.com/repos/python/mypy/git/trees/3f1695237056998f132e27a3750c9e84f48d7840
            url = json_data['tree']['url']
            status, json_data = self.git_wrapper.get(url)
            if status is None or not status.ok:
                log.info('Unable to fetch tree: {}. Skipping'.format(status))
                return -1
            tree = json_data['tree']
        except AttributeError:
            # no commit
            log.info('Unable to fetch commit {}. Skipping.'.format(build_commit_sha))
            return -1
        except KeyError:
            # no tree
            log.info('Git tree not found, commit {}. Skipping'.format(build_commit_sha))
            return -1

        build_system = 'NA'
        for file in tree:
            # assume the build file always in root, otherwise need to do this recursively(very expensive)
            # 'blob' stands for normal file
            # pom.xml => Maven, build.gradle => Gradle, build.xml => Ant
            if file['type'] == 'blob':
                if file['path'] == 'pom.xml':
                    build_system = 'Maven'
                elif file['path'] == 'build.gradle':
                    build_system = 'Gradle'
                elif file['path'] == 'build.xml':
                    build_system = 'Ant'
        return build_system
