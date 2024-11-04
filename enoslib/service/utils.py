from pathlib import Path
from typing import Optional, Union


def _to_abs(path: Path) -> Path:
    """Make sure the path is absolute."""
    _path = Path(path)
    if not _path.is_absolute():
        # prepend the cwd
        _path = Path(Path.cwd(), _path)
    return _path


def _check_path(backup_dir: Path, mkdir: Optional[bool] = True) -> Path:
    """Make sure the backup_dir is absolute and if asked, created somewhere."""
    backup_path = _to_abs(backup_dir)
    # make sure it exists
    if mkdir:
        backup_path.mkdir(parents=True, exist_ok=True)
    return backup_path


def _set_dir(
    one_dir: Optional[Union[Path, str]],
    default_dir: Union[Path, str],
    mkdir: Optional[bool] = True,
) -> Path:
    """Set directory

    Args:
        one_dir (Optional[Union[Path, str]]): New path
        default_dir (Union[Path, str]): Default path if `one_dir` is None
        mkdir (Optional[bool], optional): Mkdir the out directory. Defaults to True.

    Returns:
        Path: Absolute path to `one_dir` if not None, else `defaul_dir`
    """
    if one_dir is None:
        _dir = Path(default_dir)
    else:
        _dir = Path(one_dir)

    _dir = _check_path(_dir, mkdir)
    return _dir
