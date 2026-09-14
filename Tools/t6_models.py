"""Observed 244-byte PS3 model dependency descriptors, not model geometry."""
import struct


def read_model_reference(reader):
    header = reader.take(244)  # TEMP; the name occupies VIRTUAL memory.
    if any(header[4:]):
        raise ValueError('unsupported populated model layout')
    name = reader.string(struct.unpack_from('>I', header)[0])
    if not name or not name.startswith(',') or len(name) == 1:
        raise ValueError('expected comma-prefixed model dependency name')
    return {'name': name, 'dependency_name': name[1:], 'geometry_available': False}
