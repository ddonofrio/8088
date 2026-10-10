"""Small standard-library FAT12/FAT16 image writer and reader for DOS builds."""

from pathlib import Path
import struct


SECTOR = 512


def short_name(name):
    if name in (".", ".."):
        return name.encode().ljust(11, b" ")
    parts = name.upper().split(".")
    if len(parts) > 2 or not 1 <= len(parts[0]) <= 8 or (len(parts) == 2 and len(parts[1]) > 3):
        raise ValueError(f"Not an 8.3 filename: {name}")
    return parts[0].encode("ascii").ljust(8, b" ") + (parts[1] if len(parts) == 2 else "").encode("ascii").ljust(3, b" ")


class Writer:
    def __init__(self, size, boot, fat16=False, partitioned=False):
        self.offset = 63 if partitioned else 0
        self.total = size // SECTOR - self.offset
        self.bits = 16 if fat16 else 12
        self.spc = 4 if fat16 else (2 if size == 360 * 1024 else 1)
        self.root_entries = 512 if fat16 else (112 if size == 360 * 1024 else 224)
        self.root_sectors = self.root_entries * 32 // SECTOR
        self.spf = 1
        while True:
            clusters = (self.total - 1 - self.root_sectors - 2 * self.spf) // self.spc
            required = ((clusters + 2) * self.bits + 8 * SECTOR - 1) // (8 * SECTOR)
            if required <= self.spf:
                break
            self.spf = required
        if not (4085 <= clusters < 65525 if fat16 else clusters < 4085):
            raise ValueError("Image geometry does not match the FAT type")
        self.limit = clusters + 2
        self.next_cluster = 2
        self.cluster_size = self.spc * SECTOR
        self.data_sector = self.offset + 1 + 2 * self.spf + self.root_sectors
        self.image = bytearray(size)
        self.fat = bytearray(self.spf * SECTOR)
        media = 0xF8 if fat16 else (0xFD if size == 360 * 1024 else 0xF0)
        self.fat[:4 if fat16 else 3] = bytes([media, 255, 255, 255]) if fat16 else bytes([media, 255, 255])
        sector = bytearray(boot)
        if len(sector) != 512 or sector[510:] != b"\x55\xAA":
            raise ValueError("Invalid boot sector")
        sector[3:11] = b"FD14BOOT"
        struct.pack_into("<HBHBHHBHHHII", sector, 11,
                         512, self.spc, 1, 2, self.root_entries,
                         self.total if self.total < 65536 else 0, media, self.spf,
                         63 if fat16 else (9 if size == 360 * 1024 else 18),
                         16 if fat16 else 2, self.offset,
                         self.total if self.total >= 65536 else 0)
        sector[36:39] = bytes([0x80 if fat16 else 0, 0, 0x29])
        struct.pack_into("<I", sector, 39, 0xFD140043)
        sector[43:54] = b"FREEDOS14  "
        sector[54:62] = b"FAT16   " if fat16 else b"FAT12   "
        self.image[self.offset * 512:(self.offset + 1) * 512] = sector
        if partitioned:
            self.image[446:462] = struct.pack("<B3sB3sII", 0x80, b"\x01\x01\x00", 6, b"\xfe\xff\xff", self.offset, self.total)
            self.image[510:512] = b"\x55\xAA"

    def set_fat(self, cluster, value):
        if self.bits == 16:
            struct.pack_into("<H", self.fat, cluster * 2, value)
        else:
            index = cluster * 3 // 2
            pair = int.from_bytes(self.fat[index:index + 2], "little")
            pair = (pair & 0x000F) | (value << 4) if cluster & 1 else (pair & 0xF000) | value
            self.fat[index:index + 2] = pair.to_bytes(2, "little")

    def allocate(self, payload):
        count = max(1, (len(payload) + self.cluster_size - 1) // self.cluster_size)
        first = self.next_cluster
        if first + count > self.limit:
            raise ValueError("FAT image is full")
        for cluster in range(first, first + count):
            self.set_fat(cluster, cluster + 1 if cluster < first + count - 1 else (0xFFFF if self.bits == 16 else 0xFFF))
        start = (self.data_sector + (first - 2) * self.spc) * SECTOR
        self.image[start:start + len(payload)] = payload
        self.next_cluster += count
        return first, start

    def entry(self, name, cluster, size, directory=False):
        entry = bytearray(32)
        entry[:11] = short_name(name)
        entry[11] = 0x10 if directory else 0x20
        struct.pack_into("<H", entry, 24, (2025 - 1980) << 9 | 4 << 5 | 2)
        struct.pack_into("<HI", entry, 26, cluster, size)
        return entry

    def directory(self, tree, parent=0, root=False):
        entries = bytearray()
        if root:
            cluster = 0
            start = (self.offset + 1 + 2 * self.spf) * SECTOR
        else:
            cluster, start = self.allocate(bytes((len(tree) + 3) * 32))
            entries += self.entry(".", cluster, 0, True)
            entries += self.entry("..", parent, 0, True)
        names = set()
        for name, value in tree.items():
            key = short_name(name)
            if key in names:
                raise ValueError(f"Duplicate DOS name: {name}")
            names.add(key)
            if isinstance(value, dict):
                child = self.directory(value, cluster)
                entries += self.entry(name, child, 0, True)
            else:
                child = self.allocate(value)[0] if value else 0
                entries += self.entry(name, child, len(value))
        if root and len(entries) >= self.root_entries * 32:
            raise ValueError("Root directory is full")
        self.image[start:start + len(entries)] = entries
        return cluster

    def write(self, path, tree):
        self.directory(tree, root=True)
        for index in range(2):
            start = (self.offset + 1 + index * self.spf) * SECTOR
            self.image[start:start + len(self.fat)] = self.fat
        Path(path).write_bytes(self.image)


def source_tree(path):
    result = {}
    for item in sorted(Path(path).iterdir()):
        short_name(item.name)
        result[item.name] = source_tree(item) if item.is_dir() else item.read_bytes()
    return result


class Reader:
    def __init__(self, path):
        self.image = Path(path).read_bytes()
        self.offset = 0 if self.image[54:62].startswith(b"FAT") else struct.unpack_from("<I", self.image, 454)[0]
        self.base = self.offset * SECTOR
        bpb = self.image[self.base:self.base + SECTOR]
        self.spc = bpb[13]
        reserved = struct.unpack_from("<H", bpb, 14)[0]
        self.entries = struct.unpack_from("<H", bpb, 17)[0]
        self.spf = struct.unpack_from("<H", bpb, 22)[0]
        self.fat_start = self.base + reserved * SECTOR
        self.root_start = self.fat_start + bpb[16] * self.spf * SECTOR
        self.data_start = self.root_start + (self.entries * 32 + 511) // 512 * SECTOR
        self.bits = 16 if bpb[54:62].startswith(b"FAT16") else 12

    def chain(self, first):
        result = bytearray()
        seen = set()
        while 2 <= first < (0xFFF8 if self.bits == 16 else 0xFF8):
            if first in seen:
                raise ValueError("Cyclic FAT chain")
            seen.add(first)
            start = self.data_start + (first - 2) * self.spc * SECTOR
            result += self.image[start:start + self.spc * SECTOR]
            position = self.fat_start + (first * 2 if self.bits == 16 else first * 3 // 2)
            value = struct.unpack_from("<H", self.image, position)[0]
            first = value if self.bits == 16 else ((value >> 4) if first & 1 else value & 0xFFF)
        return bytes(result)

    def directory(self, data):
        result = {}
        for position in range(0, len(data), 32):
            entry = data[position:position + 32]
            if not entry or entry[0] == 0:
                break
            if entry[0] == 0xE5 or entry[11] & 8 or entry[0] == 46:
                continue
            stem = entry[:8].decode("ascii").rstrip()
            ext = entry[8:11].decode("ascii").rstrip()
            name = stem + ("." + ext if ext else "")
            cluster, size = struct.unpack_from("<HI", entry, 26)
            payload = self.chain(cluster) if cluster else b""
            result[name] = self.directory(payload) if entry[11] & 0x10 else payload[:size]
        return result

    def files(self):
        return self.directory(self.image[self.root_start:self.root_start + self.entries * 32])

    def update_file(self, path, name, payload):
        """Update a FAT16 file without moving files or changing build timestamps."""
        if self.bits != 16:
            raise ValueError("In-place build configuration updates require FAT16")
        image = bytearray(self.image)

        def directory_positions(cluster):
            if not cluster:
                return list(range(self.root_start, self.root_start + self.entries * 32, 32))
            positions = []
            seen = set()
            while 2 <= cluster < 0xFFF8:
                if cluster in seen:
                    raise ValueError("Cyclic FAT directory chain")
                seen.add(cluster)
                start = self.data_start + (cluster - 2) * self.spc * SECTOR
                positions.extend(range(start, start + self.spc * SECTOR, 32))
                cluster = struct.unpack_from("<H", image, self.fat_start + cluster * 2)[0]
            return positions

        parts = name.split("/")
        positions = directory_positions(0)
        for part in parts[:-1]:
            matches = [position for position in positions if image[position:position + 11] == short_name(part)]
            if len(matches) != 1 or not image[matches[0] + 11] & 0x10:
                raise FileNotFoundError(name)
            positions = directory_positions(struct.unpack_from("<H", image, matches[0] + 26)[0])
        for position in positions:
            entry = image[position:position + 32]
            if entry[:11] != short_name(parts[-1]):
                continue
            cluster = struct.unpack_from("<H", entry, 26)[0]
            locations = []
            seen = set()
            while 2 <= cluster < (0xFFF8 if self.bits == 16 else 0xFF8):
                if cluster in seen:
                    raise ValueError("Cyclic FAT chain")
                seen.add(cluster)
                locations.append(self.data_start + (cluster - 2) * self.spc * SECTOR)
                value = struct.unpack_from("<H", image, self.fat_start + cluster * 2)[0]
                cluster = value
            capacity = len(locations) * self.spc * SECTOR
            if len(payload) > capacity:
                raise ValueError(f"{name}: update exceeds the allocated file capacity")
            padded = payload.ljust(capacity, b"\0")
            for index, location in enumerate(locations):
                chunk = padded[index * self.spc * SECTOR:(index + 1) * self.spc * SECTOR]
                image[location:location + len(chunk)] = chunk
            struct.pack_into("<I", image, position + 28, len(payload))
            Path(path).write_bytes(image)
            return
        raise FileNotFoundError(name)
