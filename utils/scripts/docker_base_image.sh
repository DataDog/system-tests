#! /bin/bash
# https://rmannibucau.metawerx.net/post/docker-extracts-fileystem-with-bash
# 1.
set -eu

image="$1"
target_dir="$2"

mkdir --parent $target_dir

echo "Extracting Docker base image $image to folder $target_dir"
echo "Pas1" 
docker save -o $target_dir/image.tar $image 
echo "Pas2" 
tar xvf $target_dir/image.tar -C $target_dir
echo "Pas3" 
layers=$(jq -r '.[0].Layers[]' $target_dir/manifest.json)
echo "Pas4" 
for i in $layers; do
    tar xvf $target_dir/$i -C $target_dir
done 

#Done! clean
rm -rf $target_dir/image.tar $target_dir/manifest.json $target_dir/oci-layout  $target_dir/index.json 
rm -rf $target_dir/blobs/


