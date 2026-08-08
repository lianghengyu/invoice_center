var app = Vue.createApp({
    delimiters: ['[[', ']]'],
    data: function() {
        return {
            activeTab: 'recognize',
            // Tab1
            fileList: [],
            results: [],
            selectedIndex: 0,
            previewMap: {},
            loading: false,
            progress: 0,
            totalFiles: 0,
            previewVisible: false,
            previewUrl: '',
            jsError: '',
            debugMsg: '',
            // Tab2
            batchFileList: [],
            batchLoading: false,
            batchDone: false,
            batchError: '',
            batchMessage: ''
        };
    },
    computed: {
        buttonText: function() {
            return this.loading ? '识别中 (' + this.progress + '/' + this.totalFiles + ')' : '开始识别';
        },
        successCount: function() {
            return this.results.filter(function(r) { return !r.error; }).length;
        },
        errorCount: function() {
            return this.results.filter(function(r) { return r.error; }).length;
        },
        successResults: function() {
            return this.results.filter(function(r) { return !r.error; });
        },
        errorResults: function() {
            return this.results.filter(function(r) { return r.error; });
        },
        progressPercent: function() {
            return this.totalFiles > 0 ? Math.round((this.progress / this.totalFiles) * 100) : 0;
        },
        totalAmount: function() {
            var sum = 0;
            this.results.forEach(function(r) {
                var val = parseFloat(r.total_amount);
                if (!isNaN(val)) sum += val;
            });
            return sum > 0 ? sum.toFixed(2) : '0.00';
        }
    },
    methods: {
        handleFileChange: function(file, fileList) {
            this.fileList = fileList;
            var self = this;
            fileList.forEach(function(f) {
                if (f.raw && f.raw.type && f.raw.type.indexOf('image/') === 0 && !self.previewMap[f.name]) {
                    self.previewMap[f.name] = window.URL.createObjectURL(f.raw);
                }
            });
        },
        handleFileRemove: function(file, fileList) {
            this.fileList = fileList;
            if (file.name && this.previewMap[file.name]) {
                window.URL.revokeObjectURL(this.previewMap[file.name]);
                delete this.previewMap[file.name];
            }
        },
        handleBatchFileChange: function(file, fileList) {
            this.batchFileList = fileList;
        },
        handleBatchFileRemove: function(file, fileList) {
            this.batchFileList = fileList;
        },
        formatProgress: function() {
            return this.progress + '/' + this.totalFiles;
        },
        startRecognize: async function() {
            if (this.fileList.length === 0) return;
            this.loading = true;
            this.progress = 0;
            this.results = [];
            this.selectedIndex = 0;
            this.totalFiles = this.fileList.length;

            for (var i = 0; i < this.fileList.length; i++) {
                var file = this.fileList[i].raw;
                var fileLabel = this.fileList[i].name || (file ? file.name : '未知文件');
                var previewUrl = this.previewMap[fileLabel] || '';
                if (!file) continue;

                var formData = new FormData();
                formData.append('files', file);

                try {
                    var resp = await fetch('/api/invoice/recognize', { method: 'POST', body: formData });
                    if (!resp.ok) {
                        var errData = null;
                        try { errData = await resp.json(); } catch(e) {}
                        var msg = errData && errData.message ? errData.message : '服务端错误 (' + resp.status + ')';
                        this.results.push({ filename: fileLabel, error: msg, _previewUrl: previewUrl });
                    } else {
                        var data = await resp.json();
                        if (data.success && data.results) {
                            for (var j = 0; j < data.results.length; j++) {
                                var item = data.results[j];
                                item._previewUrl = previewUrl;
                                this.results.push(item);
                            }
                        } else {
                            this.results.push({ filename: fileLabel, error: data.message || '识别失败，未知原因', _previewUrl: previewUrl });
                        }
                    }
                } catch (err) {
                    this.results.push({ filename: fileLabel, error: '网络请求失败: ' + err.message, _previewUrl: previewUrl });
                }
                this.progress = i + 1;
            }
            this.loading = false;
            if (this.errorCount === 0) {
                ElementPlus.ElMessage.success('识别完成，共 ' + this.successCount + ' 条结果');
            } else {
                ElementPlus.ElMessage.warning('识别完成：' + this.successCount + ' 成功，' + this.errorCount + ' 失败');
            }
        },
        clearAll: function() {
            this.fileList = [];
            this.results = [];
            this.selectedIndex = 0;
            for (var key in this.previewMap) {
                window.URL.revokeObjectURL(this.previewMap[key]);
            }
            this.previewMap = {};
            if (this.$refs.uploadRef) {
                this.$refs.uploadRef.clearFiles();
            }
        },
        removeResult: function(index) {
            if (this.results[index] && this.results[index]._previewUrl) {
                window.URL.revokeObjectURL(this.results[index]._previewUrl);
            }
            this.results.splice(index, 1);
            if (this.selectedIndex >= this.results.length) {
                this.selectedIndex = this.results.length - 1;
            }
            if (this.selectedIndex < 0) {
                this.selectedIndex = 0;
            }
        },
        previewImage: function(url) {
            this.previewUrl = url;
            this.previewVisible = true;
        },
        // Tab2
        handleBatchExceed: function() {
            ElementPlus.ElMessage.warning('仅支持上传一个 Excel 文件，请先清空');
        },
        startBatchExport: async function() {
            if (this.batchFileList.length === 0) return;
            this.batchLoading = true;
            this.batchDone = false;
            this.batchError = '';

            var file = this.batchFileList[0].raw;
            var formData = new FormData();
            formData.append('file', file);

            try {
                var resp = await fetch('/api/invoice/batch-export', { method: 'POST', body: formData });
                if (!resp.ok) {
                    var errData = null;
                    try { errData = await resp.json(); } catch(e) {}
                    throw new Error(errData && errData.message ? errData.message : '服务端错误');
                }
                var blob = await resp.blob();
                var url = window.URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = '发票识别结果.xlsx';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                this.batchDone = true;
                this.batchMessage = '已从 "' + file.name + '" 中提取并识别发票，结果已下载';
                ElementPlus.ElMessage.success('导出成功');
            } catch (err) {
                this.batchError = err.message;
                ElementPlus.ElMessage.error('处理失败: ' + err.message);
            } finally {
                this.batchLoading = false;
            }
        },
        clearBatch: function() {
            this.batchFileList = [];
            this.batchDone = false;
            this.batchError = '';
            this.batchMessage = '';
            if (this.$refs.batchUploadRef) {
                this.$refs.batchUploadRef.clearFiles();
            }
        }
    }
});

for (var key in ElementPlusIconsVue) {
    app.component(key, ElementPlusIconsVue[key]);
}
app.use(ElementPlus);
app.mount('#app');
