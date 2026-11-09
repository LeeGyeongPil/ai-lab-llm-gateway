"""LLM 게이트웨이 데모 패키지.

litellm 을 import 하기 전에 환경변수를 먼저 설정해야 해서 여기서 한다.
LITELLM_LOCAL_MODEL_COST_MAP=True : 가격표를 GitHub 에서 내려받지 않고
패키지에 들어 있는 것을 쓴다 (오프라인에서도 같은 결과가 나오도록).
"""
import os

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
# litellm 의 장황한 로그를 줄인다 (표가 묻히지 않게)
os.environ.setdefault("LITELLM_LOG", "ERROR")
