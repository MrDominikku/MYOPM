from db_analysis import LotteryDatabase
from collections import Counter, defaultdict
from config import config
from heapq import nlargest, nsmallest
from itertools import combinations
import csv
import random
import time
import datetime
import math


class ConvertMain:

    def __init__(self, worker, last_draw=None, limit=0):

        # class initialize
        self.worker = worker
        self.table_name = self.worker.table_name

        if self.table_name != 'EMPTY':

            self.curr_game = config['games']['mini_lotto']

            # features
            table_headers = []
            self.features = self.curr_game['features']
            for i in range(self.worker.window.list_model.count()):
                feature_len = self.features[self.worker.window.list_model.item(i).text()]['length'] + 1
                feature_header = self.features[self.worker.window.list_model.item(i).text()]['header']
                table_headers += [feature_header + str(n) + ' INTEGER' for n in range(1, feature_len)]

            # db_initialize

            self.__table = ",".join(['ID INTEGER PRIMARY KEY'] +
                                    ['DRAFT_ID INTEGER'] + table_headers + ['LABEL INTEGER'])

            self.ldb_original = 'INPUT_' + self.curr_game['database']
            self.ldb = LotteryDatabase(config['database'])
            self.ldb.db_delete_table(self.table_name)
            self.ldb.db_create_table(self.table_name, self.__table)

            self.original_len = self.ldb.db_get_length(self.ldb_original) + 1 - limit

            # variables
            if last_draw is None:
                self.last_draw = [13, 18, 29, 32, 37]
            else:
                self.last_draw = last_draw

            self.lottery_interval = self.curr_game['length'] + 1
            self.training_size = int(self.worker.window.combo_test_size.currentText())
            self.cut = self.features['original_numbers']['length'] + 1

            self.labels = [0, 12, 34, 56]
            self.win = [1]
            self.loss = [0]

            self.rash_one = 5
            self.rash_two = 5
            self.rash_three = 5
            self.rash_default = 5

    def __append_drawn(self, current_array, set_of_six):

        new_drawn = []

        for drawn in set_of_six:
            index = drawn - 1
            new_drawn.append(current_array[index])

        return new_drawn

    def __append_rash_group(self, sample):

        new_set = []

        for num in sample:

            if num in self.curr_game['groups']['first_group']:
                new_set += [1]
            elif num in self.curr_game['groups']['second_group']:
                new_set += [2]
            elif num in self.curr_game['groups']['third_group']:
                new_set += [3]

        return new_set

    def __append_alpha_group(self, sample):

        alpha_group = []

        for n in sample:

            for g in self.curr_game['alphabetic_groups'].items():

                if n in g[1]:
                    alpha_group += [1]
                else:
                    alpha_group += [0]

        return alpha_group

    def __append_in_last_draw(self, sample, curr_draw):

        if curr_draw.count(0) == 0:
            last_draw = [0 for _ in range(1, self.lottery_interval)]
        else:
            last_draw = [1 if n in sample else 0 for n in range(1, self.lottery_interval)]

        return last_draw

    def __append_numbers_cycle(self, sample, curr_cycle):

        if curr_cycle.count(0) == 0:
            numbers_cycle = [0 for _ in range(1, self.lottery_interval)]
        else:
            numbers_cycle = [1 if n in sample else curr_cycle[n-1] for n in range(1, self.lottery_interval)]

        return numbers_cycle

    def append_hot_cold_warm_cool(self, top_numbers, n_top, large_small):

        if large_small == 'L':

            hw = nlargest(n_top, top_numbers, key=top_numbers.get)

            hc_wc = [1 if str(n) in hw else 0 for n in range(1, self.lottery_interval)]

        else:

            cc = nsmallest(n_top, top_numbers, key=top_numbers.get)

            hc_wc = [1 if str(n) in cc else 0 for n in range(1, self.lottery_interval)]

        return hc_wc

    def __append_count_label(self, sample, count_list):

        label = 0

        count = Counter(sample)
        for x in count_list:
            label = label + count[x]

        return label

    def __append_number_map(self, sample):
        return [1 if n in sample else 0 for n in range(1, self.lottery_interval)]

    def __append_rash(self, array):

        rash_group = []

        for num in array:

            if num in self.curr_game['groups']['first_group']:

                data = 1  # first_data_group.get(num)

                if data is None:
                    per = round(float(1 / self.rash_one) * 100, 2)
                else:
                    per = round(float(data / self.rash_one) * 100, 2)

                rash_group.append(per)

            elif num in self.curr_game['groups']['second_group']:

                data = 1  # second_data_group.get(num)

                if data is None:
                    per = round(float(1 / self.rash_two) * 100, 2)
                else:
                    per = round(float(data / self.rash_two) * 100, 2)
                rash_group.append(per)

            elif num in self.curr_game['groups']['third_group']:

                data = 1  # third_data_group.get(num)

                if data is None:
                    per = round(float(1 / self.rash_three) * 100, 2)
                else:
                    per = round(float(data / self.rash_three) * 100, 2)

                rash_group.append(per)

        return rash_group

    def __append_db(self, ids, *args):

        combined_set = [ids]

        for arg in args:
            combined_set = combined_set + arg

        self.ldb.db_insert(self.table_name, combined_set)

    def create_prediction_model(self, input_array):

        self.ldb = LotteryDatabase(config['database'])
        list_model = self.worker.window.list_model

        my_list = list(map(int, input_array.split(" ")))
        my_list = self.__add_random(my_list)

        ids = 1
        combined_set = []
        top_numbers = self.__create_top_numbers(self.original_len-100)
        number_cycles = self.__get_latest_number_cycle()
        curr_draw = self.__get_latest_draw()
        total_combinations = int(math.factorial(42)/(math.factorial(5)*(math.factorial(42-5))))

        for a in my_list:
            # if 1 <= a <= 11:
            for b in my_list:
                if a < b: # and 5 <= b <= 23:
                    for c in my_list:
                        if b < c: # and 11 <= c <= 33:
                            for d in my_list:
                                if c < d: # and 20 <= d <= 40:
                                    for e in my_list:
                                        diff = e-a
                                        sample_sum = a+b+c+d+e
                                        if d < e: # and 29 <= e <= 42: # and 17 < diff < 40 and 69 < sample_sum < 151:
                                            # for f in my_list:
                                            #     if e < f:

                                            sample_array = [a, b, c, d, e]

                                            for i in range(self.worker.window.list_model.count()):

                                                if list_model.item(i).text() == 'number_map':
                                                    combined_set += self.__append_number_map(sample_array)

                                                elif list_model.item(i).text() == 'number_cycles':
                                                    combined_set += self.__append_numbers_cycle(sample_array, number_cycles)

                                                elif list_model.item(i).text() == 'original_numbers':
                                                    combined_set += sample_array

                                                elif list_model.item(i).text() == 'in_last_draw':
                                                    combined_set += curr_draw

                                                elif list_model.item(i).text() == 'rash_group':
                                                    combined_set += self.__append_rash_group(sample_array)

                                                elif list_model.item(i).text() == 'alphabetic_group':
                                                    combined_set += self.__append_alpha_group(sample_array)

                                                elif list_model.item(i).text() == 'hot numbers':
                                                    combined_set += self.append_hot_cold_warm_cool(
                                                        top_numbers, 10, 'L')

                                                elif list_model.item(i).text() == 'cold numbers':
                                                    combined_set += self.append_hot_cold_warm_cool(
                                                        top_numbers, 10, 'S')

                                                elif list_model.item(i).text() == 'warm numbers':
                                                    combined_set += self.append_hot_cold_warm_cool(
                                                        top_numbers, 20, 'L')

                                                elif list_model.item(i).text() == 'cool numbers':
                                                    combined_set += self.append_hot_cold_warm_cool(
                                                        top_numbers, 20, 'S')

                                            label = [self.__append_count_label(sample_array,
                                                                               self.last_draw)]

                                            self.__append_db(ids, [0], combined_set, label)

                                            combined_set = []

                                            self.worker.signal_progress_bar.emit((ids/total_combinations)*100)

                                            ids += 1

        self.worker.signal_progress_bar.emit(0)
        self.ldb.db_commit()

    def convert_to_original(self):

        self.ldb = LotteryDatabase(config['database'])
        combo_predict = self.worker.window.combo_predict_model
        self.table_name = 'PREDICT_' + combo_predict.currentText()

        now = datetime.datetime.now()
        file_name = str.format('{} {}', combo_predict.currentText(), now.strftime("%Y-%m-%d %H %M %S"))
        export_columns = ['FIRST', 'SECOND', 'THIRD', 'FOURTH', 'FIFTH', 'SIXTH', 'LABEL', 'OUTPUT']

        with open('archived/' + file_name + '.csv', 'a', newline='') as csv_file:

            writer = csv.writer(csv_file)
            writer.writerow(export_columns)

            for o in range(1, self.original_len):
                fetch_one = list(self.ldb.db_fetchone(self.table_name, o))
                fetch_output = list(self.ldb.db_fetchone('OUTPUT_prediction', o))

                originals = fetch_one[1:50]
                label_column = [fetch_one[-1]]
                output_column = [fetch_output[-1]]

                output_list = [n + 1 for n in range(0, len(originals)) if originals[n] == 1]
                output_list = output_list + label_column + output_column

                writer.writerow(output_list)

                self.worker.signal_status.emit('Export in progress: {} of {}.'.format(o, self.original_len-1))

        self.worker.signal_status.emit('')

    def __get_latest_number_cycle(self):

        self.ldb = LotteryDatabase(config['database'])

        curr_cycle = []
        fetch_one = []

        for o in range(1, self.original_len):
            curr_cycle = self.__append_numbers_cycle(fetch_one[1:self.cut], curr_cycle)

            self.ldb.db_commit()
            fetch_one = list(self.ldb.db_fetchone(self.ldb_original, o))

        curr_cycle = self.__append_numbers_cycle(fetch_one[1:self.cut], curr_cycle)

        return curr_cycle

    def __get_latest_draw(self):

        self.ldb = LotteryDatabase(config['database'])

        curr_draw = []
        fetch_one = []

        for o in range(1, self.original_len):
            curr_draw = self.__append_in_last_draw(fetch_one[1:self.cut], curr_draw)

            self.ldb.db_commit()
            fetch_one = list(self.ldb.db_fetchone(self.ldb_original, o))

        curr_draw = self.__append_in_last_draw(fetch_one[1:self.cut], curr_draw)

        return curr_draw

    def __create_top_numbers(self, offset):

        top_numbers = {}

        sql_ct = str.format("SELECT * FROM {} limit {} offset {}", self.ldb_original, 100, offset-100)

        self.ldb.db_execute(sql_ct)
        last = self.ldb.c.fetchmany(offset)

        for sample in last:
            for s in sample[1:self.cut]:

                if str(s) not in top_numbers:
                    top_numbers[str(s)] = 0
                top_numbers[str(s)] += 1

        return top_numbers

    def get_latest_pairs(self, pair_size):

        pairs = {}

        sql_ct = str.format("SELECT * FROM {} limit {} offset {}", self.ldb_original, 366, self.original_len - 367)

        self.ldb.db_execute(sql_ct)
        last = self.ldb.c.fetchmany(self.original_len)

        for sample in last:

            comb = combinations(sample, pair_size)

            for c in comb:
                if c not in pairs:
                    pairs[c] = 1
                else:
                    pairs[c] += 1

        pairs_largest = nlargest(100, pairs, key=pairs.get)

        return pairs_largest

    def get_latest_top(self):

        self.ldb = LotteryDatabase(config['database'])

        top_numbers = self.__create_top_numbers(self.original_len-100)

        return top_numbers

    def __add_random(self, o_num):

        while True:
            r = random.randrange(1, self.lottery_interval)
            if r not in o_num:
                o_num = o_num + [r]
                if len(o_num) == 42:
                    o_num.sort()
                    break
        # self.training_size
        return o_num

    def create_training_model(self):

        self.ldb = LotteryDatabase(config['database'])
        # self.ldb.db_execute('PRAGMA synchronous=OFF')
        list_model = self.worker.window.list_model

        ids = 1
        avg_time = 0
        win_count, loss_count = 0, 0
        zero, one, two, three, four = 0, 0, 0, 0, 0
        combined_set, fetch_one, curr_cycle, curr_draw = [], [], [], []
        start_time = time.time()
        number_limit = [0, 0, 0, 0]
        
        for o in range(1, self.original_len):

            curr_cycle = self.__append_numbers_cycle(fetch_one[1:self.cut], curr_cycle)
            curr_draw = self.__append_in_last_draw(fetch_one[1:self.cut], curr_draw)
            top_numbers = self.__create_top_numbers(o)

            self.ldb.db_commit()
            fetch_one = list(self.ldb.db_fetchone(self.ldb_original, o))
            my_list = self.__add_random(fetch_one[1:self.cut])

            end_time = time.time()
            avg_time = (avg_time + (end_time - start_time)) / o
            eta = avg_time * self.original_len - avg_time * o

            self.worker.signal_status.emit(self.__print_run_time(eta))
            self.worker.signal_progress_bar.emit(((o + 1) / self.original_len) * 100)

            for a in my_list:
                for b in my_list:
                    if a < b:
                        for c in my_list:
                            if b < c:
                                for d in my_list:
                                    if c < d:
                                        for e in my_list:
                                            if d < e:
                                                # for f in my_list:
                                                #     if e < f:

                                                sample_array = [a, b, c, d, e]

                                                for i in range(self.worker.window.list_model.count()):

                                                    if list_model.item(i).text() == 'number_map':
                                                        combined_set += self.__append_number_map(sample_array)

                                                    elif list_model.item(i).text() == 'number_cycles':
                                                        combined_set += self.__append_numbers_cycle(
                                                            fetch_one[1:self.cut], curr_cycle)

                                                    elif list_model.item(i).text() == 'original_numbers':
                                                        combined_set += sample_array

                                                    elif list_model.item(i).text() == 'in_last_draw':
                                                        combined_set += curr_draw

                                                    elif list_model.item(i).text() == 'rash_group':
                                                        combined_set += self.__append_rash_group(sample_array)

                                                    elif list_model.item(i).text() == 'alphabetic_group':
                                                        combined_set += self.__append_alpha_group(sample_array)

                                                    elif list_model.item(i).text() == 'hot numbers':
                                                        combined_set += self.append_hot_cold_warm_cool(
                                                            top_numbers, 10, 'L')

                                                    elif list_model.item(i).text() == 'cold numbers':
                                                        combined_set += self.append_hot_cold_warm_cool(
                                                            top_numbers, 10, 'S')

                                                    elif list_model.item(i).text() == 'warm numbers':
                                                        combined_set += self.append_hot_cold_warm_cool(
                                                            top_numbers, 20, 'L')

                                                    elif list_model.item(i).text() == 'cool numbers':
                                                        combined_set += self.append_hot_cold_warm_cool(
                                                            top_numbers, 20, 'S')

                                                label = [self.__append_count_label(sample_array,
                                                                                   fetch_one[1:self.cut])]

                                                if self.worker.window.check_win_loss.isChecked():

                                                    if label < [3]:
                                                        self.__append_db(ids, [o], combined_set, self.loss)
                                                        loss_count += 1
                                                    else:
                                                        self.__append_db(ids, [o], combined_set, self.win)
                                                        win_count += 1

                                                    ids += 1

                                                else:

                                                    if label[0] in [0, 1]:  # and number_limit[0] < 25:
                                                        self.__append_db(ids, [o], combined_set, [0])
                                                        # number_limit[0] = number_limit[0] + 1
                                                        zero += 1
                                                        ids += 1
                                                    elif label[0] == 2:  # and number_limit[1] < 25:
                                                        self.__append_db(ids, [o], combined_set, [1])
                                                        # number_limit[1] = number_limit[1] + 1
                                                        one += 1
                                                        ids += 1
                                                    elif label[0] == 3:  # and number_limit[1] < 25:
                                                        self.__append_db(ids, [o], combined_set, [2])
                                                        # number_limit[1] = number_limit[1] + 1
                                                        two += 1
                                                        ids += 1
                                                    elif label[0] in [4, 5]:  # and number_limit[2] < 25:
                                                        self.__append_db(ids, [o], combined_set, [3])
                                                        # number_limit[2] = number_limit[2] + 1
                                                        three += 1
                                                        ids += 1

                                                combined_set = []

            number_limit = [0, 0, 0, 0]
            self.ldb.db_commit()

        if self.worker.window.check_win_loss.isChecked():
            return win_count, loss_count
        else:
            return zero, one, two, three, four

    def __print_run_time(self, seconds):

        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds - 3600 * hours) // 60
        seconds = seconds - 3600 * hours - 60 * minutes
        print_it = str.format('Estimate time remaining: {}:{}:{}'.format(
            '{:02}'.format(hours), '{:02}'.format(minutes), '{:02}'.format(seconds)))

        return print_it

    def __create_rash_group(self):

        self.ldb = LotteryDatabase(config['database'])
        fetch_a = self.ldb.db_execute(self.ldb_original)

        first_data_group = defaultdict(int)
        second_data_group = defaultdict(int)
        third_data_group = defaultdict(int)
        new_set = []

        for line in fetch_a:
            line = line[1:7]
            for num in line:
                if num in self.curr_game['groups']['first_group']:
                    new_set.append(1)
                elif num in self.curr_game['groups']['second_group']:
                    new_set.append(2)
                elif num in self.curr_game['groups']['third_group']:
                    new_set.append(3)

            count = Counter(new_set)

            if count[1] == 4:
                self.rash_one += 1
                for x, y in zip(line, new_set):
                    if y == 1:
                        first_data_group[x] += 1

            elif count[2] == 4:
                self.rash_two += 1
                for x, y in zip(line, new_set):
                    if y == 2:
                        second_data_group[x] += 1

            elif count[3] == 4:
                self.rash_three += 1
                for x, y in zip(line, new_set):
                    if y == 3:
                        third_data_group[x] += 1

            rash_group = []

            for num in line:
                if num in self.curr_game['groups']['first_group']:
                    d = first_data_group.get(num)
                    if d == "":
                        per = round(float(1 / self.rash_one) * 10, 2)
                    else:
                        per = round(float(d / self.rash_one) * 10, 2)

                    rash_group.append(per)
                elif num in self.curr_game['groups']['second_group']:
                    d = second_data_group.get(num)
                    if d == "":
                        per = round(float(1 / self.rash_two) * 10, 2)
                    else:
                        per = round(float(d / self.rash_two) * 10, 2)
                    rash_group.append(per)
                elif num in self.curr_game['groups']['third_group']:
                    d = third_data_group.get(num)
                    if d == "":
                        per = round(float(1 / self.rash_three) * 10, 2)
                    else:
                        per = round(float(d / self.rash_three) * 10, 2)

                    rash_group.append(per)

        self.ldb.__del__()
