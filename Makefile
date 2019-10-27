dotfiles: dot.py wrapper.sh
	cat wrapper.sh > $@
	cat dot.py >> $@
	echo EOF >> $@
	chmod +x $@
