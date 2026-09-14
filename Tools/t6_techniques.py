"""Observed PS3 technique metadata layouts; no shader translation or GPU objects.

This preserves observed cached and split shader byte payloads. Physical block
relocation remains unverified. PS3 programs are not translated to Metal.
"""
import hashlib
import math
import struct


def shader(reader, pointer, kind, field_address):
    if pointer == 0:
        return None
    if pointer != 0xffffffff:
        return reader.reference(kind, pointer)
    header = reader.words(4)  # TEMP shader descriptor
    populated = any(header[1:])
    split = (kind == 'pixel_shader' and header[1:3] == (0xffffffff, 0xffffffff)
             and header[3] & 0xff == 0x80)
    if populated and not split and (header[1] != 0xffffffff or header[2] != 0):
        raise ValueError('unsupported PS3 shader program pointer layout')
    result = {'name': reader.string(header[0]), 'program_available': False, 'metal_translation_available': False}
    if populated:
        if kind == 'pixel_shader':
            units = header[3] >> 16
            size = units * 16 + 16 if split else (units + 17 if header[3] & 0x8000 else units * 4 + 20)
        elif kind == 'vertex_shader':
            units = header[3] & 0xffff
            size = units * 4
        else:
            raise ValueError('unsupported shader program kind')
        if not units and not split:
            raise ValueError('zero-size populated shader program')
        if not split:
            reader.reserve(size, alignment=16)
        raw = reader.take(size)
        if split:
            reader.reserve(16, alignment=16)
            result.update(cached_descriptor_hex=reader.take(16).hex(), physical_relocation_verified=False)
        result.update(
            program_available=True, program_bytes=size,
            ps3_program_hex=raw.hex(), program_sha256=hashlib.sha256(raw).hexdigest(),
            descriptor_word=header[3],
        )
    # Asset references name the pointer slot that was fixed up by the loader.
    reader.remember(kind, field_address, result)
    return result


def declaration(reader, pointer):
    if pointer == 0:
        return None
    if pointer != 0xffffffff:
        return reader.reference('vertex_declaration', pointer)
    address = reader.reserve(34, alignment=4)
    raw = reader.take(34)
    if raw[0] > 16:
        raise ValueError('unsupported vertex declaration stream count')
    result = {'stream_count': raw[0], 'raw_layout_hex': raw.hex(), 'gpu_format_verified': False}
    reader.remember('vertex_declaration', address, result)
    return result


def literal(reader, pointer):
    if pointer == 0:
        raise ValueError('null literal constant pointer')
    if pointer != 0xffffffff:
        return reader.reference('literal_constant', pointer)
    address = reader.reserve(16, alignment=4)
    result = list(struct.unpack('>4f', reader.take(16)))
    if not all(math.isfinite(value) for value in result):
        raise ValueError('non-finite literal shader constant')
    reader.remember('literal_constant', address, result)
    return result


def arguments(reader, pointer, count):
    if not count:
        if pointer:
            raise ValueError('non-null empty shader argument array')
        return []
    if pointer != 0xffffffff:
        raise ValueError('unresolved shader argument array')
    reader.reserve(count * 8, alignment=4)
    raw = [struct.unpack('>HHI', reader.take(8)) for _ in range(count)]
    result = []
    for kind, destination, value in raw:
        if kind > 7:
            raise ValueError(f'unsupported shader argument type {kind}')
        entry = {'type': kind, 'destination': destination, 'value': value}
        if kind in (1, 7):
            entry['literal'] = literal(reader, value)
        result.append(entry)
    return result


def technique(reader, pointer):
    if pointer == 0:
        return None
    if pointer != 0xffffffff:
        return reader.reference('technique', pointer)
    name_ptr, packed = reader.words(2)
    flags, count = packed >> 16, packed & 0xffff
    if count > (len(reader.data) - reader.offset) // 40:
        raise ValueError('truncated technique pass array')
    address = reader.reserve(8 + 40 * count, alignment=4)
    raw_passes = [reader.take(40) for _ in range(count)]
    passes = []
    for index, raw in enumerate(raw_passes):
        decl_ptr, vs_ptr, ps_ptr = struct.unpack_from('>3I', raw)
        arg_counts = list(raw[12:15])
        args_ptr = struct.unpack_from('>I', raw, 36)[0]
        field = address + 8 + index * 40
        vs = shader(reader, vs_ptr, 'vertex_shader', field + 4)
        decl = declaration(reader, decl_ptr)
        ps = shader(reader, ps_ptr, 'pixel_shader', field + 8)
        passes.append({
            'vertex_shader': vs, 'vertex_declaration': decl, 'pixel_shader': ps,
            'argument_counts': arg_counts, 'raw_flags_hex': raw[15:36].hex(),
            'arguments': arguments(reader, args_ptr, sum(arg_counts)),
        })
    result = {'name': reader.string(name_ptr), 'flags': flags, 'passes': passes}
    reader.remember('technique', address, result)
    return result


def read_technique_set(reader):
    name_ptr, flags = reader.words(2)  # TEMP header, followed by 32 pointer slots
    pointers = reader.words(32)
    name = reader.string(name_ptr)
    return {
        'name': name,
        'raw_flags': flags,
        'techniques': [technique(reader, pointer) for pointer in pointers],
        'metal_translation_available': False,
    }
