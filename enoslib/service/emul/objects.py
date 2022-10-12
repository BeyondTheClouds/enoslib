from abc import ABC
from pathlib import Path
from typing import List, Tuple
from enoslib.objects import PathLike
from enoslib.service.emul.utils import FPING_FILE_SUFFIX, _fping_stats
from enoslib.service.service import Service


class BaseNetem(Service, ABC):
    @staticmethod
    def fping_stats(output_dir: PathLike) -> List[Tuple[str, str, List[float]]]:
        """Get back fping stats.

        Args:
            output_dir: Directory path to look for any fping output
                All file with the right suffix will be read

        Returns:
            list of all (alias, target, icmp rtt).
            This can be fed into a panda dataframe easily
        """
        output_dir = Path(output_dir)
        results = []
        for fping in output_dir.glob(f"*{FPING_FILE_SUFFIX}"):
            stats = _fping_stats(fping.read_text().splitlines())
            results.extend([(fping.stem, dst, s) for (dst, s) in stats])
        return results
