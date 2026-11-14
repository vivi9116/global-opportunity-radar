"""Prepare an Apache-2.0 OPUS English/Chinese model on GitHub runners only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import ssl
import urllib.request
import zipfile
import re

ROOT=Path(__file__).resolve().parents[1]
URL='https://object.pouta.csc.fi/Tatoeba-MT-models/eng-zho/opus-2020-07-17.zip'
EXPECTED_BYTES=288947487
EXPECTED_SHA256='ab90e5583fa3ec46d8c5c50f106cbd65221978cd052c7e2059981439325ae24b'

def main():
    if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('Model preparation runs on GitHub Actions only, not on the desktop.')
    import certifi
    import ctranslate2
    import yaml
    cache=ROOT/'private/offline_translation';model=cache/'model'
    if (model/'model.bin').exists() and (cache/'source.spm').exists() and (cache/'target.spm').exists():
        print('Offline translation model restored from cache.');return
    cache.mkdir(parents=True,exist_ok=True);archive=cache/'original.zip';source=cache/'original'
    context=ssl.create_default_context(cafile=certifi.where())
    request=urllib.request.Request(URL,headers={'User-Agent':'OpportunityRadar/9.3 model setup'})
    digest=hashlib.sha256();size=0
    with urllib.request.urlopen(request,context=context,timeout=90) as response,archive.open('wb') as stream:
        while chunk:=response.read(4*1024*1024):
            size+=len(chunk)
            if size>350000000:raise ValueError('Model archive exceeded the expected bound.')
            stream.write(chunk);digest.update(chunk)
    if size!=EXPECTED_BYTES:raise ValueError('Official archive size changed; review before using different model weights.')
    if digest.hexdigest()!=EXPECTED_SHA256:raise ValueError('Official archive hash changed; review before converting different model weights.')
    source.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            target=(source/entry.filename).resolve()
            if not target.is_relative_to(source.resolve()):raise ValueError('Unsafe archive path.')
        bundle.extractall(source)
    decoder=next(source.rglob('decoder.yml'));directory=decoder.parent
    config=yaml.safe_load(decoder.read_text(encoding='utf-8'))
    # Some training configurations store original absolute paths. Match files by
    # basename inside the validated official archive, never outside this folder.
    def local(name):
        candidate=directory/Path(name).name
        if candidate.exists():return candidate
        return next(source.rglob(Path(name).name))
    model_file=local(config['models'][0]);vocabs=[local(name) for name in config['vocabs']]
    converter=ctranslate2.converters.MarianConverter(str(model_file),[str(path) for path in vocabs])
    converter.convert(str(model),quantization='int8',force=True)
    for name in ['source.spm','target.spm']:
        original=next(source.rglob(name));shutil.copy2(original,cache/name)
    import sentencepiece as spm
    source_sp=spm.SentencePieceProcessor(model_file=str(cache/'source.spm'));target_sp=spm.SentencePieceProcessor(model_file=str(cache/'target.spm'))
    translator=ctranslate2.Translator(str(model),device='cpu',compute_type='int8',intra_threads=2)
    sample='I need someone to clean two CSV files. My budget is 60 dollars.'
    result=translator.translate_batch([['>>cmn_Hans<<']+source_sp.encode(sample,out_type=str)],beam_size=2)[0]
    chinese=target_sp.decode(result.hypotheses[0])
    if not re.search(r'[\u4e00-\u9fff]',chinese) or '60' not in chinese:raise ValueError('Offline translation smoke test failed; review language token and model.')
    print('OFFLINE_MODEL_SMOKE_TEST:',chinese)
    (cache/'provenance.json').write_text(json.dumps({'original_url':URL,'archive_sha256':digest.hexdigest(),'archive_bytes':size,'model':'Helsinki-NLP/opus-mt-en-zh / eng-zho','license':'Apache-2.0','target_language_token':'>>cmn_Hans<<','quantization':'int8'},indent=2),encoding='utf-8')
    if not source.resolve().is_relative_to(cache.resolve()):raise ValueError('Unsafe cleanup target.')
    shutil.rmtree(source);archive.unlink()
    print(json.dumps({'model_ready':True,'download_bytes':size,'archive_sha256':digest.hexdigest(),'cached_bytes':sum(file.stat().st_size for file in cache.rglob('*') if file.is_file())}))

if __name__=='__main__':main()
