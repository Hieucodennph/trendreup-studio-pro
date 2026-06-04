from downloaders.base import YtDlpDownloader


class YouTubeDownloader(YtDlpDownloader):
    platform = "youtube"


class KwaiDownloader(YtDlpDownloader):
    platform = "kwai"


class LikeeDownloader(YtDlpDownloader):
    platform = "likee"


class TwitterDownloader(YtDlpDownloader):
    platform = "twitter"


class GenericDownloader(YtDlpDownloader):
    platform = "auto"
