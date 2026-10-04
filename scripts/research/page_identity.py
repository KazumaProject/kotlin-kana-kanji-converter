"""Verified contemporary page-ID identity evidence; never pronunciation proof."""
import gzip,hashlib,json,pathlib,re,sqlite3
import worker as w

def parse_sql_tuple(value: str) -> list[str | None]:
    """Parse one MySQL/MariaDB VALUES tuple without executing SQL."""
    fields: list[str | None] = []
    index = 0
    length = len(value)
    escapes = {
        "0": "\0",
        "b": "\b",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "Z": "\x1a",
        "\\": "\\",
        "'": "'",
        '"': '"',
    }
    while index < length:
        while index < length and value[index] in " \t,":
            index += 1
        if index >= length:
            break
        if value[index] == "'":
            index += 1
            chars: list[str] = []
            while index < length:
                char = value[index]
                if char == "\\":
                    index += 1
                    if index >= length:
                        raise ValueError("dangling backslash in SQL string")
                    chars.append(escapes.get(value[index], value[index]))
                    index += 1
                elif char == "'":
                    if index + 1 < length and value[index + 1] == "'":
                        chars.append("'")
                        index += 2
                    else:
                        index += 1
                        break
                else:
                    chars.append(char)
                    index += 1
            else:
                raise ValueError("unterminated SQL string")
            fields.append("".join(chars))
        else:
            start = index
            while index < length and value[index] not in ",)":
                index += 1
            token = value[start:index].strip()
            fields.append(None if token.upper() == "NULL" else token)
        while index < length and value[index] in " \t":
            index += 1
        if index < length and value[index] == ",":
            index += 1
        elif index < length and value[index] != ")":
            raise ValueError(f"unexpected SQL tuple character: {value[index]!r}")
    return fields


def iter_insert_rows(path: pathlib.Path, table: str):
    """Yield parsed tuple rows from a standard Wikimedia SQL dump."""
    quote = chr(96)
    prefix = "INSERT INTO " + quote + table + quote + " VALUES"
    in_values = False
    found = False
    # pp_value is a binary blob column, and unrelated properties can contain
    # non-UTF8 bytes. A reversible byte lexer is appropriate here; the retained
    # page IDs, property name and Wikibase QIDs must all be ASCII.
    with gzip.open(path, "rt", encoding="latin-1", errors="strict", newline="") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.startswith(prefix):
                in_values = True
                found = True
                continue
            if not in_values:
                continue
            stripped = line.strip()
            if not stripped:
                continue
            if stripped == ";":
                in_values = False
                continue
            if not stripped.startswith("("):
                continue
            if stripped.endswith(","):
                tuple_text = stripped[:-1]
            elif stripped.endswith(";"):
                tuple_text = stripped[:-1]
                in_values = False
            else:
                tuple_text = stripped
            if not tuple_text.endswith(")"):
                raise ValueError(f"{path}:{line_number}: incomplete SQL tuple")
            yield parse_sql_tuple(tuple_text[1:-1])
    if not found:
        raise ValueError(f"no INSERT VALUES block for table {table} in {path}")


def build(source,output,expected_sha1,url):
    source=pathlib.Path(source);sha1=hashlib.sha1()
    with source.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):sha1.update(block)
    if sha1.hexdigest()!=expected_sha1:raise ValueError('Official page_props checksum mismatch')
    metadata={'source':str(source.resolve()),'url':url,'sha1':expected_sha1,'sha256':w.sha(source),'bytes':source.stat().st_size,'complete':False}
    path=pathlib.Path(output);db=sqlite3.connect(path)
    try:
        db.executescript('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE IF NOT EXISTS page_identity(page_id INTEGER PRIMARY KEY,qid TEXT,quotation TEXT);')
        previous=db.execute("SELECT value FROM meta WHERE key='source'").fetchone()
        if previous:
            saved=json.loads(previous[0])
            if saved['sha256']!=metadata['sha256']:raise ValueError('Identity index already contains another source')
            if saved.get('complete'):return saved
        db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('source',w.canonical(metadata)));db.commit();count=0
        for fields in iter_insert_rows(source,'page_props'):
            if len(fields)!=4:raise ValueError('Unexpected page_props tuple schema')
            if fields[1]!='wikibase_item':continue
            if not re.fullmatch('Q[0-9]+',fields[2] or ''):raise ValueError('Invalid Wikibase page identity')
            # Identity-only tuple reconstruction is exact for these unescaped
            # integer/property/QID fields. No SQL is executed from the source.
            quote="("+str(int(fields[0]))+",'wikibase_item','"+fields[2]+"',"+('NULL' if fields[3] is None else fields[3])+")"
            db.execute('INSERT OR REPLACE INTO page_identity VALUES(?,?,?)',(int(fields[0]),fields[2],quote));count+=1
            if count%10000==0:db.commit()
        metadata.update({'complete':True,'pageIdentities':count});db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('source',w.canonical(metadata)));db.commit();return metadata
    finally:db.close()


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--expected-sha1',required=True);p.add_argument('--url',required=True);a=p.parse_args();w.emit(build(a.source,a.output,a.expected_sha1,a.url))
