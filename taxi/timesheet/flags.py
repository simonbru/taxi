class FlaggableMixin(object):
    FLAG_IGNORED = 1
    FLAG_PUSHED = 2

    def __init__(self, *args, **kwargs):
        self._flags = set()
        super(FlaggableMixin, self).__init__(*args, **kwargs)

    def add_flag(self, flag):
        self._flags.add(flag)

    def remove_flag(self, flag):
        self._flags.remove(flag)

    @property
    def ignored(self):
        return self.FLAG_IGNORED in self._flags

    @property
    def pushed(self):
        return self.FLAG_PUSHED in self._flags

    @ignored.setter
    def ignored(self, value):
        meth = self.add_flag if value else self.remove_flag
        meth(self.FLAG_IGNORED)

    @pushed.setter
    def pushed(self, value):
        meth = self.add_flag if value else self.remove_flag
        meth(self.FLAG_PUSHED)
