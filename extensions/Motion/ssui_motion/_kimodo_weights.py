"""Pinned public artifacts used by the small-memory Mac Kimodo workflow."""
import hashlib
import json
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

ARTIFACTS = (
    ('nvidia/Kimodo-SOMA-RP-v1.1','6c9233af1180b8151e3c4703477104af5dce9dd5','Kimodo-SOMA-RP-v1.1'),
    # Community distribution of the same Llama-3 Instruct + MNTP base, not an
    # official NVIDIA encoder checkpoint. Its Llama license still applies.
    ('raducius/Llama-3-8B-Instruct-LLM2Vec-mntp-merged','61c9d7b02d40b7a770807c0a4e17a3ece59ccd27','text-base'),
    ('McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp-supervised','baa8ebf04a1c2500e61288e7dad65e8ae42601a7','text-adapter'),
)


def download_weights(root):
    records=[]
    for repo, revision, folder in ARTIFACTS:
        print('Pinned artifact:',repo,revision,flush=True)
        info=HfApi().model_info(repo,revision=revision,files_metadata=True)
        path=Path(snapshot_download(repo,revision=revision,local_dir=Path(root)/folder,
                  allow_patterns=['*.json','*.safetensors','*.npy','*.yaml','*.jinja','LICENSE','NOTICE','README.md','THIRD_PARTY_LICENSES/*']))
        hashes={}
        for file in info.siblings:
            if file.lfs and (path/file.rfilename).is_file():
                with (path/file.rfilename).open('rb') as stream:
                    digest=hashlib.file_digest(stream,'sha256').hexdigest()
                if digest != file.lfs.sha256: raise RuntimeError(f'Checksum failed: {file.rfilename}')
                hashes[file.rfilename]=digest
        records.append(dict(repository=repo,revision=revision,sha256=hashes))
    (Path(root)/'provenance.json').write_text(json.dumps(records,indent=2)+'\n')
    print('Pinned artifacts downloaded and LFS hashes verified',flush=True)
