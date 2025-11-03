## 技術選定など

-   Yolo v5 モデルをベースにファインチューニングしたモデルを利用する。

-   Programming language: Python（version 3.1.x）

-   lib deps management tool: poetry

## 搭載基盤（物理）

-   Raspberry Pi 5（16GB memory, 64GB SSD）

-

## クラウド先選定情報メモ（by AI）

### 結論

aws または gcp サービスを利用。一旦慣れている google colab で作業

### メモ

主要クラウドサービスの GPU 利用における代表的な料金目安は以下の通りです。価格は 1 時間あたりのオンデマンド料金を概算しています（2025 年末情報基準）。実際は使用時間やリージョン、割引、スポット使用の有無で変動します。

サービス名 GPU タイプ 料金目安（USD/時間） 備考
Google Compute Engine (GCE) NVIDIA Tesla T4 約 $0.45〜$0.60 通常利用。NVIDIA A100 等は更に高価
Google Vertex AI Workbench a2-highgpu-1g (NVIDIA A100 1 基) 約 $4.22 高性能 GPU。用途により複数 GPU も利用可
AWS EC2 (G4dn) NVIDIA Tesla T4 約 $0.75 中程度性能。P4d(A100)は更に高価
AWS EC2 (P4d) NVIDIA A100 約 $32 ハイエンド GPU、多くの AI 用途向け
AWS SageMaker G4dn インスタンス 約 $1.10 マネージド ML サービス
Microsoft Azure NV シリーズ NVIDIA Tesla M60 約 $0.90〜1.20 VM タイプによる
Microsoft Azure NC シリーズ NVIDIA Tesla K80 約 $0.70〜1.00 VM タイプによる
Google Colab Pro - 月額約 $10（時間制限あり） 連続利用制限あり。手軽な実験向け
Paperspace - $0.45〜$0.90 GPU タイプによる。従量課金
ポイント
高性能 GPU（NVIDIA A100 等）を使うと 1 時間あたり数十ドルになることもあるため、本格運用はコスト計算が重要です。

個人の実験用途なら Google Colab Pro や Paperspace の低コストレンタルがおすすめ。

AWS や GCP のオンデマンド GPU 利用は自由度高いがコスト高め。

予算と目的でサービスを選ぶのが良いです。
