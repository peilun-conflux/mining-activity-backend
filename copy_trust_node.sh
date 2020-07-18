date=`date +"%Y.%m.%d"`
echo "date is" $date
db_dir="trusted_nodes/$date"
mkdir -p $db_dir
while read line
do
  a=($line)
  user=${a[0]}
  ip=${a[1]}
  dir=${a[2]}
  echo $ip
  scp $user@$ip:$dir/net_config/trusted_nodes.json $db_dir/$ip-trusted_nodes.json
done < host_work_dirs
python3 count_trusted_node.py